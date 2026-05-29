"""1688 抓取器（DOM 无关：扫所有 a 取商品 ID，扫所有 img 取图片）."""
from __future__ import annotations

import re
import time
from urllib.parse import urlparse, parse_qs

from loguru import logger

from .base import BaseScraper, Product
from .utils import encode_keyword, parse_price


SEARCH_URL = "https://s.1688.com/selloffer/offer_search.htm?keywords={kw}&beginPage={page}"
DETAIL_URL = "https://detail.1688.com/offer/{pid}.html"
HOME_URL = "https://www.1688.com/"

# 兼容多种 href 形式
ID_RE = re.compile(r"(?:^|//|/)(?:detail(?:\.m)?\.1688\.com)?/offer/(\d{6,})\.html")
ID_IN_HTML_RE = re.compile(r'(?:offerId|data-offer-id)["\']?\s*[:=]\s*["\']?(\d{8,})')

# 1688 / 阿里图片 CDN（涵盖几乎所有商品图）
IMG_HOST_RE = re.compile(r"(alicdn|taobaocdn|tbcdn|aliimg|1688|gd\d+\.alicdn)", re.I)
# 从 HTML 源码里直接抓阿里图片 URL
IMG_URL_IN_HTML_RE = re.compile(
    r'(?:https?:)?//[^"\'\s<>]*?(?:alicdn|aliimg|tbcdn|taobaocdn)[^"\'\s<>]*?\.(?:jpg|jpeg|png|webp|gif)',
    re.I,
)
# 形如 .summ. / _100x100. / _220x220q90.jpg 的缩略图标记
THUMB_SIZE_RE = re.compile(r"(_\d+x\d+(?:q\d+)?|\.summ)\.")


def _normalize_img_url(url: str) -> str:
    """补协议、去缩略图后缀。"""
    if not url:
        return url
    if url.startswith("//"):
        url = "https:" + url
    url = THUMB_SIZE_RE.sub(".", url)
    return url


def _is_alicdn_image(url: str) -> bool:
    if not url or not url.startswith(("http", "//")):
        return False
    if not IMG_HOST_RE.search(url):
        return False
    # 排除 logo、icon 之类的小图
    lower = url.lower()
    if any(s in lower for s in ("logo", "icon", "avatar", "1x1", "spacer")):
        return False
    return True


def _img_attrs(img_el) -> list[str]:
    """从 <img> 上读所有可能的图片地址属性（懒加载常用 data-*）。"""
    out = []
    for attr in ("src", "data-src", "data-original", "data-lazy-src", "data-ks-lazyload",
                 "data-image", "data-srcset", "srcset"):
        try:
            v = img_el.attr(attr)
        except Exception:
            continue
        if not v:
            continue
        # srcset 形如 "url1 1x, url2 2x"
        if " " in v and "," in v:
            for part in v.split(","):
                u = part.strip().split(" ")[0]
                if u:
                    out.append(u)
        else:
            out.append(v)
    return out


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

            if not self.ensure_logged_in(page, target_url=url, timeout_each_load=timeout):
                logger.warning("[1688] 用户取消或未通过登录，跳过该关键词。")
                break

            try:
                logger.info(f"[1688] 当前页：{page.url}")
                logger.info(f"[1688] 页面标题：{page.title}")
            except Exception:
                pass

            offer_map = self._extract_offers(page)
            n_with_img = sum(1 for v in offer_map.values() if v.get("images"))
            logger.info(f"[1688] 第 {page_no} 页提取到 {len(offer_map)} 个商品，其中 {n_with_img} 个带图")

            if not offer_map:
                try:
                    html = (page.html or "")[:1500]
                    logger.warning(f"[1688] 0 件！页面 HTML 片段：{html}")
                except Exception:
                    pass
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
                    images=info.get("images") or [],
                )
                if len(collected) >= limit:
                    break
            if len(collected) >= limit:
                break

        logger.info(f"[1688] 关键词 '{keyword}' 共采集 {len(collected)} 条")
        return list(collected.values())[:limit]

    def _extract_offers(self, page) -> dict[str, dict]:
        result: dict[str, dict] = {}

        # 策略 1：扫所有 <a>
        try:
            anchors = page.eles("css:a")
        except Exception:
            anchors = []
        for a in anchors:
            try:
                href = a.attr("href") or ""
            except Exception:
                continue
            m = ID_RE.search(href)
            if not m:
                continue
            pid = m.group(1)
            if pid in result:
                continue

            # 标题
            try:
                title = (a.attr("title") or a.text or "").strip()
                if not title:
                    img = a.ele("css:img", timeout=0.3)
                    title = (img.attr("alt") if img else "") or ""
            except Exception:
                title = ""

            # 价格 + 图片：在卡片容器里找
            container = a
            try:
                p = a.parent()
                if p:
                    container = p
                    p2 = p.parent()
                    if p2:
                        container = p2  # 再往上一层抓得更全
            except Exception:
                pass

            price_text, price = None, None
            try:
                price_el = container.ele("css:[class*='price'], [class*='Price']", timeout=0.3)
                if price_el:
                    price_text = price_el.text.strip()
                    price = parse_price(price_text)
            except Exception:
                pass

            # 图片：扫卡片里所有 <img>
            imgs = self._collect_images_in(container, max_n=3)

            result[pid] = {
                "title": title,
                "url": href if href.startswith("http") else DETAIL_URL.format(pid=pid),
                "price": price,
                "price_text": price_text,
                "images": imgs,
            }

        if result:
            return result

        # 策略 2：HTML 源码 regex
        try:
            html = page.html or ""
        except Exception:
            html = ""
        for m in ID_IN_HTML_RE.finditer(html):
            pid = m.group(1)
            if pid in result:
                continue
            result[pid] = {
                "title": "", "url": DETAIL_URL.format(pid=pid),
                "price": None, "price_text": None, "images": [],
            }
        return result

    @staticmethod
    def _collect_images_in(container, max_n: int = 5) -> list[str]:
        out: list[str] = []
        try:
            imgs = container.eles("css:img")
        except Exception:
            imgs = []
        for img_el in imgs:
            for u in _img_attrs(img_el):
                if _is_alicdn_image(u):
                    nu = _normalize_img_url(u)
                    if nu and nu not in out:
                        out.append(nu)
                        break
            if len(out) >= max_n:
                break
        return out

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

        # 滚动让懒加载图出来
        for _ in range(2):
            try:
                page.scroll.to_bottom()
            except Exception:
                pass
            time.sleep(0.6)
        try:
            page.scroll.to_top()
        except Exception:
            pass

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

        # ===== 图片：DOM 无关三层兜底 =====
        imgs: list[str] = list(product.images)  # 保留搜索页已抓到的

        # 1) 扫所有 <img>
        try:
            for img in page.eles("css:img"):
                for u in _img_attrs(img):
                    if _is_alicdn_image(u):
                        nu = _normalize_img_url(u)
                        if nu not in imgs:
                            imgs.append(nu)
                        break
                if len(imgs) >= 10:
                    break
        except Exception:
            pass

        # 2) 从 HTML 源码 regex 抓
        if len(imgs) < 5:
            try:
                html = page.html or ""
            except Exception:
                html = ""
            for m in IMG_URL_IN_HTML_RE.finditer(html):
                u = m.group(0)
                nu = _normalize_img_url(u)
                if _is_alicdn_image(nu) and nu not in imgs:
                    imgs.append(nu)
                if len(imgs) >= 15:
                    break

        product.images = imgs[:10]

        # 规格
        specs: dict[str, str] = {}
        for row in page.eles("css:.offer-attr-list li, .od-pc-attribute li, .obj-content li, [class*='attribute'] li, [class*='property'] li, dl dt, dl dd, table tr"):
            text = row.text.strip()
            sep = ":" if ":" in text else ("：" if "：" in text else None)
            if sep:
                k, _, v = text.partition(sep)
                k, v = k.strip(), v.strip()
                if k and v and len(k) < 30 and len(v) < 200:
                    specs[k] = v
        product.specs = specs

        # 从 specs 抽常用字段
        for key in ("品牌", "产地", "材质", "起订量", "MOQ", "发货期"):
            if key in specs:
                if key == "品牌": product.brand = specs[key]
                elif key == "产地": product.origin = specs[key]
                elif key == "材质": product.material = specs[key]
                elif key in ("起订量", "MOQ"): product.moq = specs[key]
                elif key == "发货期": product.delivery = specs[key]

        # 描述：抓详情页正文（限 3000 字）
        desc_parts: list[str] = []
        for el in page.eles("css:#desc-content, .detail-content, [class*='desc-content'], [class*='description'], .od-pc-detail-content"):
            try:
                t = el.text.strip()
            except Exception:
                t = ""
            if t and t not in desc_parts:
                desc_parts.append(t)
            if sum(len(x) for x in desc_parts) > 3000:
                break
        product.description = "\n".join(desc_parts)[:3000]

        # 卖点
        features: list[str] = []
        for el in page.eles("css:.mod-detail-features li, .feature-list li, .selling-point li, [class*='feature'] li"):
            t = el.text.strip()
            if t:
                features.append(t)
        if not features and specs:
            features = [f"{k}: {v}" for k, v in list(specs.items())[:5]]
        product.features = features

        crumbs = [c.text.strip() for c in page.eles("css:.breadcrumb a, .crumb a, [class*='breadcrumb'] a") if c.text.strip()]
        if crumbs:
            product.category_path = " > ".join(crumbs)

        shop_el = page.ele("css:.shop-name, .company-name, .od-pc-shop-name, [class*='shop-name']", timeout=1)
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
        return self.fetch_detail(Product(
            platform=self.name, product_id=pid, title="",
            url=DETAIL_URL.format(pid=pid),
        ))
