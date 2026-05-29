"""1688 抓取器."""
from __future__ import annotations

import re
from urllib.parse import quote_plus, urlparse, parse_qs

from loguru import logger

from .base import BaseScraper, Product
from .utils import parse_price, sleep_random


SEARCH_URL = "https://s.1688.com/selloffer/offer_search.htm?keywords={kw}&beginPage={page}"
DETAIL_URL = "https://detail.1688.com/offer/{pid}.html"
HOME_URL = "https://www.1688.com/"

ID_RE = re.compile(r"/offer/(\d+)\.html")


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
            url = SEARCH_URL.format(kw=quote_plus(keyword), page=page_no)
            logger.info(f"[1688] 搜索 {keyword} 第 {page_no} 页")
            try:
                page.get(url, timeout=timeout)
            except Exception as exc:
                logger.warning(f"[1688] 页面加载失败：{exc}")
                continue

            sleep_random(self.config["browser"]["request_interval"])

            # 检测登录 / 验证页，必要时阻塞等待用户
            if not self.ensure_logged_in(page, target_url=url, timeout_each_load=timeout):
                logger.warning("[1688] 用户取消或未通过登录，跳过该关键词。")
                break

            cards = page.eles("css:a[href*='detail.1688.com/offer/']")
            if not cards:
                logger.warning(f"[1688] 第{page_no}页没找到商品卡片（可能页面结构变化或仍被风控）。")
                continue

            for a in cards:
                href = a.attr("href") or ""
                m = ID_RE.search(href)
                if not m:
                    continue
                pid = m.group(1)
                if pid in collected:
                    continue
                title = (a.attr("title") or a.text or "").strip()
                if not title:
                    img = a.ele("css:img", timeout=0.5)
                    title = (img.attr("alt") if img else "") or ""
                collected[pid] = Product(
                    platform=self.name,
                    product_id=pid,
                    title=title.strip(),
                    url=DETAIL_URL.format(pid=pid),
                    keyword=keyword,
                )
                if len(collected) >= limit:
                    break

            if len(collected) >= limit:
                break

        logger.info(f"[1688] 关键词 '{keyword}' 共采集 {len(collected)} 条")
        return list(collected.values())[:limit]

    # ---------------- 详情 ----------------
    def fetch_detail(self, product: Product) -> Product:
        page = self.tab
        timeout = self.config["browser"].get("page_load_timeout", 30)
        try:
            page.get(product.url, timeout=timeout)
        except Exception as exc:
            logger.warning(f"[1688] 详情加载失败 {product.url}: {exc}")
            return product
        sleep_random(self.config["browser"]["request_interval"])

        if not self.ensure_logged_in(page, target_url=product.url, timeout_each_load=timeout):
            return product

        # 标题
        title_el = page.ele("css:h1", timeout=2) or page.ele(
            "css:.d-title, .title-text, .od-pc-offer-title", timeout=2
        )
        if title_el and title_el.text.strip():
            product.title = title_el.text.strip()

        # 价格
        price_el = page.ele(
            "css:.price, .mod-detail-price, [class*='price']", timeout=2
        )
        if price_el:
            product.price_text = price_el.text.strip().replace("\n", " ")
            product.price = parse_price(product.price_text)

        # 图片
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

        # 规格
        specs: dict[str, str] = {}
        for row in page.eles("css:.offer-attr-list li, .od-pc-attribute li, .obj-content li"):
            text = row.text.strip()
            sep = ":" if ":" in text else ("：" if "：" in text else None)
            if sep:
                k, _, v = text.partition(sep)
                specs[k.strip()] = v.strip()
        product.specs = specs

        # 卖点
        features: list[str] = []
        for el in page.eles("css:.mod-detail-features li, .feature-list li, .selling-point li"):
            t = el.text.strip()
            if t:
                features.append(t)
        if not features and specs:
            features = [f"{k}: {v}" for k, v in list(specs.items())[:5]]
        product.features = features

        # 类目
        crumbs = [c.text.strip() for c in page.eles("css:.breadcrumb a, .crumb a") if c.text.strip()]
        if crumbs:
            product.category_path = " > ".join(crumbs)

        shop_el = page.ele("css:.shop-name, .company-name, .od-pc-shop-name", timeout=1)
        if shop_el:
            product.shop = shop_el.text.strip()

        return product

    # ---------------- URL 直采 ----------------
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
