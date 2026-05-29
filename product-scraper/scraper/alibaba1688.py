"""1688 抓取器（DOM 无关：扫描所有 <a> 用 regex 匹配商品 ID）."""
from __future__ import annotations

import json
import re
import time
from urllib.parse import urlparse, parse_qs

from loguru import logger

from .base import BaseScraper, Product
from .utils import encode_keyword, parse_price, sleep_random


SEARCH_URL = "https://s.1688.com/selloffer/offer_search.htm?keywords={kw}&beginPage={page}"
DETAIL_URL = "https://detail.1688.com/offer/{pid}.html"
HOME_URL = "https://www.1688.com/"

# 匹配多种格式的 1688 商品 ID
# https://detail.1688.com/offer/12345.html
# //detail.1688.com/offer/12345.html
# /offer/12345.html
# https://detail.m.1688.com/offer/12345.html
ID_RE = re.compile(r"(?:^|//|/)(?:detail(?:\.m)?\.1688\.com)?/offer/(\d{6,})\.html")
# 兜底：HTML 源码里 "offerId":"12345" / data-offer-id="12345"
ID_IN_HTML_RE = re.compile(r'(?:offerId|data-offer-id)["\']?\s*[:=]\s*["\']?(\d{8,})')


class Alibaba1688Scraper(BaseScraper):
    name = "alibaba1688"
    home_url = HOME_URL

    # ---------------- 搜索 ----------------
    def search(self, keyword: str, max_pages: int, limit: int) -> list[Product]:
        page = self.tab
        collected: dict[str, Product] = {}
        timeout = self.config["browser"].get("page_load_timeout", 30)

        for page_no in range(1, max_pages + 1):
            if self.controller and self.controller.is_stopping():
                break
            url = SEARCH_URL.format(kw=encode_keyword(keyword, "gbk"), page=page_no)
            logger.info(f"[1688] 加载搜索页 {page_no}：{url}")
            try:
                page.get(url, timeout=timeout)
            except Exception as exc:
                logger.warning(f"[1688] 搜索页加载失败：{exc}")
                continue

            # 给 JS 一点时间渲染 + 滚动触发懒加载
            time.sleep(2.0)
            for _ in range(3):
                try:
                    page.scroll.to_bottom()
                except Exception:
                    pass
                time.sleep(0.8)
            try:
                page.scroll.to_top()
            except Exception:
                pass

            # 检查登录/验证状态
            if not self.ensure_logged_in(page, target_url=url, timeout_each_load=timeout):
                logger.warning("[1688] 用户取消或未通过登录，跳过该关键词。")
                break

            # ===== 多策略抓商品 ID =====
            try:
                logger.info(f"[1688] 当前页：{page.url}")
                logger.info(f"[1688] 页面标题：{page.title}")
            except Exception:
                pass

            offer_map: dict[str, dict] = self._extract_offers(page)
            logger.info(f"[1688] 第 {page_no} 页提取到 {len(offer_map)} 个商品")

            if not offer_map:
                # dump 一段 HTML 帮助定位（前 2000 字符）
                try:
                    html = (page.html or "")[:2000]
                    logger.warning(f"[1688] 0 件！页面 HTML 片段：{html[:1500]}")
                except Exception:
                    pass
                logger.warning(
                    "[1688] 没找到商品。可能原因："
                    "1) 还没在 Tab 里登录；2) 1688 改了页面结构；"
                    "3) 风控页伪装成搜索页。请在浏览器 1688 Tab 手动确认能看到商品列表。"
                )
                continue

            for pid, info in offer_map.items():
                if pid in collected:
                    continue
                collected[pid] = Product(
                    platform=self.name,
                    product_id=pid,
                    title=info.get("title", "").strip(),
                    url=info.get("url") or DETAIL_URL.format(pid=pid),
                    keyword=keyword,
                    price=info.get("price"),
                    price_text=info.get("price_text"),
                )
                if len(collected) >= limit:
                    break
            if len(collected) >= limit:
                break

        logger.info(f"[1688] 关键词 '{keyword}' 共采集 {len(collected)} 条")
        return list(collected.values())[:limit]

    def _extract_offers(self, page) -> dict[str, dict]:
        """
        多策略提取商品。返回 {offer_id: {title, url, price, price_text}}。
        策略 1：扫描所有 <a> 标签的 href，regex 匹配 offer ID
        策略 2：扫描页面 HTML 源码，regex 匹配 offerId / data-offer-id
        """
        result: dict[str, dict] = {}

        # --- 策略 1：扫所有 <a> ---
        try:
            anchors = page.eles("css:a")
        except Exception:
            anchors = []
        for a in anchors:
            try:
                href = a.attr("href") or ""
            except Exception:
                continue
            if not href:
                continue
            m = ID_RE.search(href)
            if not m:
                continue
            pid = m.group(1)
            if pid in result:
                continue
            try:
                title = (a.attr("title") or a.text or "").strip()
                if not title:
                    img = a.ele("css:img", timeout=0.3)
                    title = (img.attr("alt") if img else "") or ""
            except Exception:
                title = ""
            # 试着在父元素里找价格
            price_text, price = None, None
            try:
                container = a.parent() or a
                price_el = container.ele("css:[class*='price'], [class*='Price']", timeout=0.3)
                if price_el:
                    price_text = price_el.text.strip()
                    price = parse_price(price_text)
            except Exception:
                pass
            result[pid] = {
                "title": title,
                "url": href if href.startswith("http") else DETAIL_URL.format(pid=pid),
                "price": price,
                "price_text": price_text,
            }

        if result:
            return result

        # --- 策略 2：从源码中正则 ---
        try:
            html = page.html or ""
        except Exception:
            html = ""
        for m in ID_IN_HTML_RE.finditer(html):
            pid = m.group(1)
            if pid in result:
                continue
            result[pid] = {
                "title": "",
                "url": DETAIL_URL.format(pid=pid),
                "price": None,
                "price_text": None,
            }
        return result

    # ---------------- 详情 ----------------
    def fetch_detail(self, product: Product) -> Product:
        page = self.tab
        timeout = self.config["browser"].get("page_load_timeout", 30)
        try:
            page.get(product.url, timeout=timeout)
        except Exception as exc:
            logger.warning(f"[1688] 详情加载失败 {product.url}: {exc}")
            return product
        time.sleep(1.5)

        if not self.ensure_logged_in(page, target_url=product.url, timeout_each_load=timeout):
            return product

        title_el = page.ele("css:h1", timeout=2) or page.ele(
            "css:.d-title, .title-text, .od-pc-offer-title", timeout=2
        )
        if title_el and title_el.text.strip():
            product.title = title_el.text.strip()

        price_el = page.ele(
            "css:.price, .mod-detail-price, [class*='price']", timeout=2
        )
        if price_el:
            product.price_text = price_el.text.strip().replace("\n", " ")
            product.price = parse_price(product.price_text)

        imgs: list[str] = []
        for img in page.eles("css:.detail-gallery img, .od-pc-gallery img, .img-list img"):
            src = img.attr("src") or img.attr("data-src") or ""
            if src and "http" in src:
                src = re.sub(r"_\d+x\d+\.", ".", src)
                if src not in imgs:
                    imgs.append(src)
            if len(imgs) >= 10:
                break
        product.images = imgs

        specs: dict[str, str] = {}
        for row in page.eles("css:.offer-attr-list li, .od-pc-attribute li, .obj-content li"):
            text = row.text.strip()
            sep = ":" if ":" in text else ("：" if "：" in text else None)
            if sep:
                k, _, v = text.partition(sep)
                specs[k.strip()] = v.strip()
        product.specs = specs

        features: list[str] = []
        for el in page.eles("css:.mod-detail-features li, .feature-list li, .selling-point li"):
            t = el.text.strip()
            if t:
                features.append(t)
        if not features and specs:
            features = [f"{k}: {v}" for k, v in list(specs.items())[:5]]
        product.features = features

        crumbs = [c.text.strip() for c in page.eles("css:.breadcrumb a, .crumb a") if c.text.strip()]
        if crumbs:
            product.category_path = " > ".join(crumbs)

        shop_el = page.ele("css:.shop-name, .company-name, .od-pc-shop-name", timeout=1)
        if shop_el:
            product.shop = shop_el.text.strip()

        return product

    def parse_url(self, url: str) -> Product | None:
        m = ID_RE.search(url)
        if m:
            pid = m.group(1)
        else:
            qs = parse_qs(urlparse(url).query)
            pid = qs.get("offerId", [None])[0]
            if not pid:
                return None
        prod = Product(
            platform=self.name,
            product_id=pid,
            title="",
            url=DETAIL_URL.format(pid=pid),
        )
        return self.fetch_detail(prod)
