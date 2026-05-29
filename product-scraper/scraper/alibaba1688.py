"""1688 抓取器：基于 DrissionPage 的浏览器渲染方式."""
from __future__ import annotations

import re
from urllib.parse import quote_plus, urlparse, parse_qs

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

from .base import BaseScraper, Product
from .utils import parse_price, sleep_random


SEARCH_URL = "https://s.1688.com/selloffer/offer_search.htm?keywords={kw}&beginPage={page}"
DETAIL_URL = "https://detail.1688.com/offer/{pid}.html"

# 商品 ID 提取（兼容多种链接形式）
ID_RE = re.compile(r"/offer/(\d+)\.html")


class Alibaba1688Scraper(BaseScraper):
    name = "alibaba1688"

    # ---------------- 搜索 ----------------
    def search(self, keyword: str, max_pages: int, limit: int) -> list[Product]:
        page = self.browser.latest_tab
        collected: dict[str, Product] = {}

        for page_no in range(1, max_pages + 1):
            url = SEARCH_URL.format(kw=quote_plus(keyword), page=page_no)
            logger.info(f"[1688] 搜索 {keyword} 第 {page_no} 页 -> {url}")
            try:
                page.get(url, timeout=self.config["browser"]["page_load_timeout"])
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[1688] 页面加载失败：{exc}")
                continue

            sleep_random(self.config["browser"]["request_interval"])
            self._maybe_handle_captcha(page)

            # 1688 搜索结果卡片：data-h5-href 或 a[href*='detail.1688.com/offer/']
            cards = page.eles("css:a[href*='detail.1688.com/offer/']")
            if not cards:
                logger.warning("[1688] 未找到商品卡片，可能命中风控或页面结构变化。")
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
                    # 兜底：取卡片内的图片 alt
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
    @retry(stop=stop_after_attempt(2), wait=wait_fixed(2), reraise=False)
    def fetch_detail(self, product: Product) -> Product:
        page = self.browser.latest_tab
        logger.info(f"[1688] 详情 {product.product_id} -> {product.url}")
        page.get(product.url, timeout=self.config["browser"]["page_load_timeout"])
        sleep_random(self.config["browser"]["request_interval"])
        self._maybe_handle_captcha(page)

        # 标题（详情页可能更完整）
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

        # 主图 / 缩略图
        imgs: list[str] = []
        for img in page.eles("css:.detail-gallery img, .od-pc-gallery img, .img-list img"):
            src = img.attr("src") or img.attr("data-src") or ""
            if src and "http" in src:
                # 1688 缩略图常带 _\d+x\d+ 后缀，去掉拿原图
                src = re.sub(r"_\d+x\d+\.", ".", src)
                if src not in imgs:
                    imgs.append(src)
            if len(imgs) >= 10:
                break
        product.images = imgs

        # 规格 / SKU
        specs: dict[str, str] = {}
        for row in page.eles("css:.offer-attr-list li, .od-pc-attribute li, .obj-content li"):
            text = row.text.strip()
            if ":" in text:
                k, _, v = text.partition(":")
                specs[k.strip()] = v.strip()
            elif "：" in text:
                k, _, v = text.partition("：")
                specs[k.strip()] = v.strip()
        product.specs = specs

        # 卖点 / 特点
        features: list[str] = []
        for el in page.eles("css:.mod-detail-features li, .feature-list li, .selling-point li"):
            t = el.text.strip()
            if t:
                features.append(t)
        # 兜底：把规格里前几个比较短的值当特点
        if not features and specs:
            features = [f"{k}: {v}" for k, v in list(specs.items())[:5]]
        product.features = features

        # 类目（面包屑）
        crumbs = [c.text.strip() for c in page.eles("css:.breadcrumb a, .crumb a") if c.text.strip()]
        if crumbs:
            product.category_path = " > ".join(crumbs)

        # 店铺
        shop_el = page.ele("css:.shop-name, .company-name, .od-pc-shop-name", timeout=1)
        if shop_el:
            product.shop = shop_el.text.strip()

        return product

    # ---------------- URL 直采 ----------------
    def parse_url(self, url: str) -> Product | None:
        m = ID_RE.search(url)
        if not m:
            # 兼容 m.1688.com 或带 query 的链接
            qs = parse_qs(urlparse(url).query)
            pid = qs.get("offerId", [None])[0]
            if not pid:
                return None
        else:
            pid = m.group(1)
        prod = Product(
            platform=self.name,
            product_id=pid,
            title="",
            url=DETAIL_URL.format(pid=pid),
        )
        return self.fetch_detail(prod)

    # ---------------- 风控辅助 ----------------
    def _maybe_handle_captcha(self, page) -> None:
        """检测到滑块/验证页时，提示用户人工处理后回车继续。"""
        url = page.url or ""
        if "punish" in url or "captcha" in url or "login" in url:
            logger.warning("[1688] 触发风控/登录页，请在浏览器中完成验证后回车继续...")
            try:
                input()
            except EOFError:
                pass
