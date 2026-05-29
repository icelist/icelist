"""数据落地：JSON / Excel（按"类型"分 Sheet）/ 图片下载."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
from loguru import logger
from tqdm import tqdm

from .base import Product
from .utils import download_image, safe_filename


class Storage:
    def __init__(self, output_cfg: dict):
        self.dir = Path(output_cfg.get("dir", "output"))
        self.dir.mkdir(parents=True, exist_ok=True)
        self.images_dir = Path(output_cfg.get("images_dir", self.dir / "images"))
        self.write_excel = output_cfg.get("excel", True)
        self.write_json = output_cfg.get("json", True)

    # ---------- 图片 ----------
    def download_images_for(self, products: Iterable[Product]) -> None:
        for p in tqdm(list(products), desc="下载图片"):
            sub = self.images_dir / p.platform / safe_filename(
                p.bucket_type or "未分类"
            ) / safe_filename(p.product_id)
            local = []
            for idx, url in enumerate(p.images):
                path = download_image(url, sub, prefix=f"{idx:02d}")
                if path:
                    local.append(path)
            p.local_images = local

    # ---------- 导出 ----------
    def save(self, products: list[Product]) -> dict[str, str]:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        results: dict[str, str] = {}

        if not products:
            logger.warning("没有可保存的商品。")
            return results

        rows = [self._flatten(p) for p in products]
        df = pd.DataFrame(rows)

        if self.write_json:
            jpath = self.dir / f"products_{ts}.json"
            jpath.write_text(
                json.dumps([p.to_dict() for p in products], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            results["json"] = str(jpath)
            logger.info(f"已写入 JSON: {jpath}")

        if self.write_excel:
            xpath = self.dir / f"products_{ts}.xlsx"
            with pd.ExcelWriter(xpath, engine="openpyxl") as writer:
                # 总表
                df.to_excel(writer, sheet_name="ALL", index=False)
                # 按"类型"分 Sheet
                for type_name, sub_df in df.groupby("bucket_type", dropna=False):
                    sheet = safe_filename(str(type_name) or "未分类", max_len=28)
                    sub_df.to_excel(writer, sheet_name=sheet, index=False)
                # 按"价格区间"再来一份
                for bucket, sub_df in df.groupby("bucket_price", dropna=False):
                    sheet = f"价_{safe_filename(str(bucket), max_len=24)}"
                    sub_df.to_excel(writer, sheet_name=sheet, index=False)
            results["excel"] = str(xpath)
            logger.info(f"已写入 Excel: {xpath}")

        return results

    @staticmethod
    def _flatten(p: Product) -> dict:
        d = p.to_dict()
        d["images"] = " | ".join(p.images)
        d["local_images"] = " | ".join(p.local_images)
        d["features"] = " | ".join(p.features)
        d["specs"] = " | ".join(f"{k}:{v}" for k, v in p.specs.items())
        return d
