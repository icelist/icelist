"""拼多多 抓取器：走移动端站点，反爬强度更低、结构更稳定."""
from __future__ import annotations

import json
import re
from urllib.parse import quote_plus, urlparse, parse_qs

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

from .base import BaseScraper, Product
from .utils import parse_price, sleep_random


# 注：拼多多 PC 站强反爬，走 mobile.yangkeduo.com 更稳定（也是其官方站点别名）
SEARCH_URL = "https://mobile.yangkeduo.com/search_result.html?search_key={kw}&page={page}"
DETAIL_URL = "https://mobile.yangkeduo.com/goods.html?goods_id={pid}"

ID_RE = re.compile(r"goods_id=(\d+)")
RAW_DATA_RE = re.compile(r"window\.rawData\s*=\s*(\{.+?\});", re.S)


class PinduoduoScraper(BaseScraper):
    name = "pinduoduo"

    # ---------------- 搜索 ----------------
    def search(self, keyword: str, max_pages: int, limit: int) -> list[Product]:
        page = self.browser.latest_tab
        collected: dict[str, Product] = {}

        for page_no in range(1, max_pages + 1):
            url = SEARCH_URL.format(kw=quote_plus(keyword), page=page_no)
            logger.info(f"[PDD] 搜索 {keyword} 第 {page_no} 页 -> {url}")
            try:
                page.get(url, timeout=self.config["browser"]["page_load_timeout"])
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[PDD] 页面加载失败：{exc}")
                continue

            sleep_random(self.config["browser"]["request_interval"])
            self._maybe_handle_captcha(page)

            # 滚动以触发懒加载
            for _ in range(4):
                page.scroll.to_bottom()
                sleep_random([0.6, 1.2])

            # 商品卡片 a 标签
            anchors = page.eles("css:a[href*='goods.html?goods_id=']")
            if not anchors:
                logger.warning("[PDD] 未找到商品卡片，可能命中风控。")
                continue

            for a in anchors:
                href = a.attr("href") or ""
                m = ID_RE.search(href)
                if not m:
                    continue
                pid = m.group(1)
                if pid in collected:
                    continue

                title = (a.attr("title") or "").strip()
                if not title:
                    # 卡片内通常有标题文本块
                    title_el = a.ele("css:.goods-name, .name, [class*='title']", timeout=0.3)
                    if title_el:
                        title = title_el.text.strip()
                    else:
                        title = a.text.strip().split("\n")[0]

                # 卡片内价格（搜索页价格更准，详情页可能要登录）
                price_text = None
                price = None
                price_el = a.ele("css:[class*='price']", timeout=0.3)
                if price_el:
                    price_text = price_el.text.strip()
                    price = parse_price(price_text)

                collected[pid] = Product(
                    platform=self.name,
                    product_id=pid,
                    title=title,
                    url=DETAIL_URL.format(pid=pid),
                    keyword=keyword,
                    price=price,
                    price_text=price_text,
                )
                if len(collected) >= limit:
                    break

            if len(collected) >= limit:
                break

        logger.info(f"[PDD] 关键词 '{keyword}' 共采集 {len(collected)} 条")
        return list(collected.values())[:limit]

    # ---------------- 详情 ----------------
    @retry(stop=stop_after_attempt(2), wait=wait_fixed(2), reraise=False)
    def fetch_detail(self, product: Product) -> Product:
        page = self.browser.latest_tab
        logger.info(f"[PDD] 详情 {product.product_id} -> {product.url}")
        page.get(product.url, timeout=self.config["browser"]["page_load_timeout"])
        sleep_random(self.config["browser"]["request_interval"])
        self._maybe_handle_captcha(page)

        # 优先解析 window.rawData（PDD 把全部数据塞这里），失败再走 DOM
        html = page.html or ""
        raw = self._extract_raw_data(html)
        if raw:
            self._fill_from_raw(product, raw)
        else:
            self._fill_from_dom(page, product)

        return product

    # ---------------- URL 直采 ----------------
    def parse_url(self, url: str) -> Product | None:
        qs = parse_qs(urlparse(url).query)
        pid = qs.get("goods_id", [None])[0] or qs.get("goodsId", [None])[0]
        if not pid:
            m = ID_RE.search(url)
            pid = m.group(1) if m else None
        if not pid:
            return None
        prod = Product(
            platform=self.name,
            product_id=pid,
            title="",
            url=DETAIL_URL.format(pid=pid),
        )
        return self.fetch_detail(prod)

    # ---------------- 内部 ----------------
    @staticmethod
    def _extract_raw_data(html: str) -> dict | None:
        m = RAW_DATA_RE.search(html)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None

    def _fill_from_raw(self, product: Product, raw: dict) -> None:
        """从 rawData 中提取关键字段（结构可能版本变化，做防御式取值）。"""
        store = raw.get("store") or raw.get("initDataObj") or {}
        # 不同版本路径不同，做几次尝试
        goods = (
            store.get("data", {}).get("ssrData", {}).get("storeInfo", {}).get("goods")
            or store.get("data", {}).get("goods")
            or store.get("goods")
            or {}
        )
        if not goods:
            # 退化：递归搜索包含 goodsName 的字典
            goods = self._deep_find_goods(raw) or {}

        if not goods:
            return

        product.title = goods.get("goodsName") or product.title
        # 价格分（PDD 普遍以分为单位）
        min_price = goods.get("minOnSaleGroupPrice") or goods.get("minGroupPrice")
        max_price = goods.get("maxOnSaleGroupPrice") or goods.get("maxGroupPrice")
        if isinstance(min_price, (int, float)):
            product.price = round(min_price / 100, 2)
            if isinstance(max_price, (int, float)) and max_price != min_price:
                product.price_text = f"{product.price} - {round(max_price / 100, 2)}"
            else:
                product.price_text = f"{product.price}"

        # 图片
        gallery = goods.get("viewImageData") or goods.get("topGallery") or []
        if isinstance(gallery, list):
            product.images = [g if isinstance(g, str) else g.get("url", "") for g in gallery if g][:10]

        # 规格
        specs = goods.get("goodsProperty") or goods.get("propertyInfoList") or []
        spec_dict: dict[str, str] = {}
        if isinstance(specs, list):
            for item in specs:
                k = item.get("key") or item.get("name")
                vals = item.get("values") or item.get("value")
                if isinstance(vals, list):
                    vals = ",".join(str(v) for v in vals)
                if k:
                    spec_dict[str(k)] = str(vals or "")
        product.specs = spec_dict

        # 特点 / 卖点
        features = goods.get("goodsDesc") or goods.get("sellingPoint") or []
        if isinstance(features, str):
            features = [features]
        product.features = [f for f in features if f][:10]

        # 类目
        cat = goods.get("catName") or goods.get("category")
        if cat:
            product.category_path = str(cat)

        # 店铺
        mall = raw.get("store", {}).get("data", {}).get("ssrData", {}).get("mallInfo") or {}
        product.shop = mall.get("mallName") or product.shop

        # 销量
        sales = goods.get("salesTip") or goods.get("sideSalesTip")
        if sales:
            product.sales = str(sales)

    def _deep_find_goods(self, obj) -> dict | None:
        if isinstance(obj, dict):
            if "goodsName" in obj and "goodsId" in obj:
                return obj
            for v in obj.values():
                r = self._deep_find_goods(v)
                if r:
                    return r
        elif isinstance(obj, list):
            for v in obj:
                r = self._deep_find_goods(v)
                if r:
                    return r
        return None

    def _fill_from_dom(self, page, product: Product) -> None:
        """rawData 拿不到时的兜底解析。"""
        title_el = page.ele("css:.goods-name, h1, [class*='title']", timeout=2)
        if title_el and title_el.text.strip():
            product.title = title_el.text.strip()

        price_el = page.ele("css:[class*='price']", timeout=2)
        if price_el:
            product.price_text = price_el.text.strip().replace("\n", " ")
            product.price = parse_price(product.price_text)

        imgs = []
        for img in page.eles("css:img"):
            src = img.attr("src") or img.attr("data-src") or ""
            if "pdd" in src and src.startswith("http"):
                if src not in imgs:
                    imgs.append(src)
            if len(imgs) >= 10:
                break
        product.images = imgs

    def _maybe_handle_captcha(self, page) -> None:
        url = page.url or ""
        html = (page.html or "")[:500]
        if "captcha" in url or "login" in url or "验证" in html:
            logger.warning("[PDD] 触发风控/登录，请在浏览器中处理后回车继续...")
            try:
                input()
            except EOFError:
                pass
