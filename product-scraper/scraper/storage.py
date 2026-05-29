"""数据落地：JSON / Excel（按"类型"+"价格区间"分 Sheet）/ 图片下载.

v1.1 更新：Excel 第一列嵌入真实图片缩略图（不再是 URL）。
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Iterable

from loguru import logger
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from tqdm import tqdm

from .base import Product
from .utils import download_image, safe_filename

# Pillow 必有，但稳一点也做兜底
try:
    from PIL import Image as PILImage
    HAS_PIL = True
except Exception:  # noqa: BLE001
    HAS_PIL = False


# ============== 常量 ==============
THUMB_SIZE = 90               # 缩略图像素
EXCEL_ROW_HEIGHT = 70         # Excel 行高 pt（≈ 90px）
PREVIEW_COL_WIDTH = 14        # 第一列宽度（字符数，足够装 90px 图）

HEADER_FILL = PatternFill(start_color="FF1F2937", end_color="FF1F2937", fill_type="solid")
HEADER_FONT = Font(color="FFFFFFFF", bold=True)


# Excel 列定义 - 第一列是"图片预览"（嵌入图片），后面是文本字段
PREVIEW_KEY = "_preview"
COLUMNS: list[tuple[str, str, object]] = [
    (PREVIEW_KEY,       "图片预览",    None),  # 特殊：嵌入图片
    ("platform",        "平台",        lambda p: p.platform),
    ("product_id",      "商品ID",      lambda p: p.product_id),
    ("title",           "标题",        lambda p: p.title or ""),
    ("price",           "价格",        lambda p: p.price if p.price is not None else ""),
    ("price_text",      "价格文案",    lambda p: p.price_text or ""),
    ("bucket_type",     "类型",        lambda p: p.bucket_type or ""),
    ("bucket_price",    "价格区间",    lambda p: p.bucket_price or ""),
    ("category_path",   "平台类目",    lambda p: p.category_path or ""),
    ("shop",            "店铺",        lambda p: p.shop or ""),
    ("sales",           "销量",        lambda p: p.sales or ""),
    ("keyword",         "搜索关键词",  lambda p: p.keyword or ""),
    ("features",        "卖点/特点",   lambda p: " | ".join(p.features)),
    ("specs",           "规格",        lambda p: " | ".join(f"{k}:{v}" for k, v in p.specs.items())),
    ("images",          "图片URL",     lambda p: " | ".join(p.images)),
    ("local_images",    "本地图片",    lambda p: " | ".join(p.local_images)),
    ("url",             "详情链接",    lambda p: p.url),
]

COL_WIDTHS = {
    PREVIEW_KEY: PREVIEW_COL_WIDTH,
    "platform": 12, "product_id": 16, "title": 50, "price": 10, "price_text": 14,
    "bucket_type": 12, "bucket_price": 12, "category_path": 24, "shop": 20,
    "sales": 12, "keyword": 14, "features": 40, "specs": 40,
    "images": 40, "local_images": 40, "url": 50,
}


def _make_excel_thumb_bytes(src_path: str) -> bytes | None:
    """读本地图，生成 ~90x90 PNG 字节流。失败返回 None。"""
    if not HAS_PIL or not src_path:
        return None
    try:
        with PILImage.open(src_path) as img:
            img.thumbnail((THUMB_SIZE, THUMB_SIZE), PILImage.LANCZOS)
            if img.mode in ("RGBA", "LA", "P"):
                bg = PILImage.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")
            buf = BytesIO()
            img.save(buf, format="PNG", optimize=True)
            return buf.getvalue()
    except Exception as exc:
        logger.warning(f"生成缩略图失败 {src_path}: {exc}")
        return None


class Storage:
    def __init__(self, output_cfg: dict):
        self.dir = Path(output_cfg.get("dir", "output"))
        self.dir.mkdir(parents=True, exist_ok=True)
        self.images_dir = Path(output_cfg.get("images_dir", self.dir / "images"))
        self.write_excel = output_cfg.get("excel", True)
        self.write_json = output_cfg.get("json", True)

    # ---------- 图片下载 ----------
    def download_images_for(self, products: Iterable[Product]) -> None:
        products = list(products)
        ok_count = 0
        for p in tqdm(products, desc="下载图片"):
            try:
                sub = self.images_dir / safe_filename(p.platform) / safe_filename(
                    p.bucket_type or "未分类"
                ) / safe_filename(p.product_id)
                local = []
                for idx, url in enumerate(p.images or []):
                    try:
                        path = download_image(url, sub, prefix=f"{idx:02d}")
                        if path:
                            local.append(path)
                    except Exception as exc:
                        logger.warning(f"下载图片异常 {url}: {exc}")
                p.local_images = local
                if local:
                    ok_count += 1
            except Exception as exc:
                logger.warning(f"处理 {p.product_id} 图片异常：{exc}")
        logger.info(f"图片下载完成：{ok_count}/{len(products)} 件商品至少存到 1 张图")

    # ---------- 导出 ----------
    def save(self, products: list[Product]) -> dict[str, str]:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        results: dict[str, str] = {}

        if not products:
            logger.warning("没有可保存的商品。")
            return results

        if self.write_json:
            jpath = self.dir / f"products_{ts}.json"
            try:
                jpath.write_text(
                    json.dumps([p.to_dict() for p in products], ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                results["json"] = str(jpath)
                logger.info(f"已写入 JSON: {jpath}")
            except Exception as exc:
                logger.error(f"写 JSON 失败 {jpath}: {exc}")

        if self.write_excel:
            xpath = self.dir / f"products_{ts}.xlsx"
            try:
                self._write_excel(xpath, products)
                results["excel"] = str(xpath)
                logger.info(f"已写入 Excel（含嵌入图片）: {xpath}")
            except PermissionError:
                alt = self.dir / f"products_{ts}_新.xlsx"
                logger.warning(f"Excel 文件被占用，改写到 {alt.name}")
                try:
                    self._write_excel(alt, products)
                    results["excel"] = str(alt)
                    logger.info(f"已写入 Excel: {alt}")
                except Exception as exc:
                    logger.error(f"写 Excel 失败 {alt}: {exc}")
            except Exception as exc:
                logger.error(f"写 Excel 失败 {xpath}: {exc}")

        return results

    # ---------- Excel ----------
    def _write_excel(self, path: Path, products: list[Product]) -> None:
        wb = Workbook()
        ws_all = wb.active
        ws_all.title = "ALL"
        self._fill_sheet(ws_all, products)

        # 按"类型"分 Sheet
        by_type: dict[str, list[Product]] = defaultdict(list)
        for p in products:
            by_type[p.bucket_type or "未分类"].append(p)
        for type_name, items in by_type.items():
            sheet_name = safe_filename(type_name, max_len=28) or "未分类"
            sheet_name = self._unique_name(wb, sheet_name)
            ws = wb.create_sheet(sheet_name)
            self._fill_sheet(ws, items)

        # 按"价格区间"分 Sheet
        by_bucket: dict[str, list[Product]] = defaultdict(list)
        for p in products:
            by_bucket[p.bucket_price or "未知"].append(p)
        for bucket, items in by_bucket.items():
            sheet_name = self._unique_name(wb, f"价_{safe_filename(bucket, max_len=24)}")
            ws = wb.create_sheet(sheet_name)
            self._fill_sheet(ws, items)

        wb.save(path)

    @staticmethod
    def _unique_name(wb: Workbook, base: str) -> str:
        name = base[:31] or "Sheet"
        existing = set(wb.sheetnames)
        if name not in existing:
            return name
        i = 2
        while f"{name[:28]}_{i}" in existing:
            i += 1
        return f"{name[:28]}_{i}"

    @staticmethod
    def _fill_sheet(ws, items: list[Product]) -> None:
        # ---------- 表头 ----------
        for col_idx, (_key, title, _fn) in enumerate(COLUMNS, start=1):
            cell = ws.cell(row=1, column=col_idx, value=title)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.freeze_panes = "B2"

        # ---------- 列宽 ----------
        for col_idx, (key, _title, _fn) in enumerate(COLUMNS, start=1):
            ws.column_dimensions[get_column_letter(col_idx)].width = COL_WIDTHS.get(key, 16)

        embedded_count = 0
        for row_idx, p in enumerate(items, start=2):
            # 行高（容纳图片）
            ws.row_dimensions[row_idx].height = EXCEL_ROW_HEIGHT

            # 第一列：嵌入图片
            preview_path = ""
            if p.local_images:
                preview_path = p.local_images[0]
            if preview_path:
                thumb = _make_excel_thumb_bytes(preview_path)
                if thumb:
                    try:
                        xlimg = XLImage(BytesIO(thumb))
                        xlimg.width = THUMB_SIZE
                        xlimg.height = THUMB_SIZE
                        anchor = f"A{row_idx}"
                        ws.add_image(xlimg, anchor)
                        embedded_count += 1
                    except Exception as exc:
                        logger.warning(f"嵌入图片失败 {p.product_id}: {exc}")

            # 其它列：常规取值
            for col_idx, (key, _title, fn) in enumerate(COLUMNS, start=1):
                if key == PREVIEW_KEY:
                    continue
                try:
                    val = fn(p) if fn else ""
                except Exception:
                    val = ""
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.alignment = Alignment(vertical="center", wrap_text=False)

        if items:
            ws.auto_filter.ref = ws.dimensions
        if embedded_count:
            logger.info(f"  Sheet '{ws.title}'：嵌入 {embedded_count} 张图片")
