"""拼多多 抓取器（移动端站点）."""
from __future__ import annotations

import json
import re
from urllib.parse import quote_plus, urlparse, parse_qs

from loguru import logger

from .base import BaseScraper, Product
from .utils import parse_price, sleep_random


SEARCH_URL = "https://mobile.yangkeduo.com/search_result.html?search_key={kw}&page={page}"
DETAIL_URL = "https://mobile.yangkeduo.com/goods.html?goods_id={pid}"
HOME_URL = "https://mobile.yangkeduo.com/"

ID_RE = re.compile(r"goods_id=(\d+)")
RAW_DATA_RE = re.compile(r"window\.rawData\s*=\s*(\{.+?\});", re.S)


class PinduoduoScraper(BaseScraper):
    name = "pinduoduo"
    home_url = HOME_URL

    def is_login_page(self, page) -> bool:
        # PDD 经常用反爬验证页（JS challenge），URL 也可能不变；多看 html 关键词
        if super().is_login_page(page):
            return True
        try:
            html = (page.html or "")[:3000]
        except Exception:
            html = ""
        return any(k in html for k in ("anti_content", "请进行验证", "验证码"))

    # ---------------- 搜索 ----------------
    def search(self, keyword: str, max_pages: int, limit: int) -> list[Product]:
        import time
        page = self.tab
        collected: dict[str, Product] = {}
        timeout = self.config["browser"].get("page_load_timeout", 30)

        for page_no in range(1, max_pages + 1):
            if self.controller and self.controller.is_stopping():
                break
            url = SEARCH_URL.format(kw=quote_plus(keyword), page=page_no)
            logger.info(f"[PDD] 加载搜索页 {page_no}：{url}")
            try:
                page.get(url, timeout=timeout)
            except Exception as exc:
                logger.warning(f"[PDD] 搜索页加载失败：{exc}")
                continue
            time.sleep(2.0)

            if not self.ensure_logged_in(page, target_url=url, timeout_each_load=timeout):
                logger.warning("[PDD] 用户取消或未通过登录。")
                break

            for _ in range(5):
                try:
                    page.scroll.to_bottom()
                except Exception:
                    pass
                sleep_random([0.6, 1.2])

            anchors = page.eles("css:a[href*='goods.html?goods_id=']")
            try:
                logger.info(f"[PDD] 当前页：{page.url}")
                logger.info(f"[PDD] 页面标题：{page.title}")
            except Exception:
                pass
            logger.info(f"[PDD] 第 {page_no} 页找到 {len(anchors)} 个商品卡片")

            if not anchors:
                logger.warning(
                    "[PDD] 没找到商品卡片。可能原因："
                    "1) 你还没在 PDD Tab 登录；"
                    "2) PDD 反爬触发；"
                    "3) 搜索结果为空。"
                    "请在 PDD Tab 手动确认能看到商品列表，再点【已完成】重试。"
                )
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
                    title_el = a.ele("css:.goods-name, .name, [class*='title']", timeout=0.3)
                    title = title_el.text.strip() if title_el else a.text.strip().split("\n")[0]

                price_text, price = None, None
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
    def fetch_detail(self, product: Product) -> Product:
        page = self.tab
        timeout = self.config["browser"].get("page_load_timeout", 30)
        try:
            page.get(product.url, timeout=timeout)
        except Exception as exc:
            logger.warning(f"[PDD] 详情加载失败 {product.url}: {exc}")
            return product
        sleep_random(self.config["browser"]["request_interval"])

        if not self.ensure_logged_in(page, target_url=product.url, timeout_each_load=timeout):
            return product

        try:
            html = page.html or ""
        except Exception:
            html = ""
        raw = self._extract_raw_data(html)
        if raw:
            self._fill_from_raw(product, raw)
        else:
            self._fill_from_dom(page, product)
        return product

    def parse_url(self, url: str) -> Product | None:
        qs = parse_qs(urlparse(url).query)
        pid = qs.get("goods_id", [None])[0] or qs.get("goodsId", [None])[0]
        if not pid:
            m = ID_RE.search(url)
            pid = m.group(1) if m else None
        if not pid:
            return None
        return self.fetch_detail(Product(
            platform=self.name, product_id=pid, title="",
            url=DETAIL_URL.format(pid=pid),
        ))

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
        store = raw.get("store") or raw.get("initDataObj") or {}
        goods = (
            store.get("data", {}).get("ssrData", {}).get("storeInfo", {}).get("goods")
            or store.get("data", {}).get("goods")
            or store.get("goods")
            or {}
        )
        if not goods:
            goods = self._deep_find_goods(raw) or {}
        if not goods:
            return

        product.title = goods.get("goodsName") or product.title
        min_p = goods.get("minOnSaleGroupPrice") or goods.get("minGroupPrice")
        max_p = goods.get("maxOnSaleGroupPrice") or goods.get("maxGroupPrice")
        if isinstance(min_p, (int, float)):
            product.price = round(min_p / 100, 2)
            if isinstance(max_p, (int, float)) and max_p != min_p:
                product.price_text = f"{product.price} - {round(max_p / 100, 2)}"
            else:
                product.price_text = f"{product.price}"

        gallery = goods.get("viewImageData") or goods.get("topGallery") or []
        if isinstance(gallery, list):
            product.images = [g if isinstance(g, str) else g.get("url", "") for g in gallery if g][:10]

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

        features = goods.get("goodsDesc") or goods.get("sellingPoint") or []
        if isinstance(features, str):
            features = [features]
        product.features = [f for f in features if f][:10]

        cat = goods.get("catName") or goods.get("category")
        if cat:
            product.category_path = str(cat)
        mall = raw.get("store", {}).get("data", {}).get("ssrData", {}).get("mallInfo") or {}
        product.shop = mall.get("mallName") or product.shop
        sales = goods.get("salesTip") or goods.get("sideSalesTip")
        if sales:
            product.sales = str(sales)

    def _deep_find_goods(self, obj):
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
            if "pdd" in src and src.startswith("http") and src not in imgs:
                imgs.append(src)
            if len(imgs) >= 10:
                break
        product.images = imgs
