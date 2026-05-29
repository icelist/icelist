"""后台工作线程：驱动 scraper，避免 GUI 卡死."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from scraper.alibaba1688 import Alibaba1688Scraper
from scraper.base import Product
from scraper.classifier import classify_products
from scraper.pinduoduo import PinduoduoScraper
from scraper.utils import sleep_random


SCRAPER_REGISTRY = {
    "alibaba1688": Alibaba1688Scraper,
    "pinduoduo": PinduoduoScraper,
}


class ScrapeWorker(QThread):
    """跑抓取的后台线程。"""

    log = Signal(str, str)                   # level, msg
    progress = Signal(int, int, str)         # current, total, msg
    product_done = Signal(object)            # Product
    finished_ok = Signal(list)               # list[Product] 全部成果
    failed = Signal(str)                     # 错误信息

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    # ----------- run -----------
    def run(self) -> None:  # noqa: C901
        cfg = self.cfg
        results: list[Product] = []
        browser = None
        try:
            self.log.emit("INFO", "正在启动浏览器...")
            browser = self._build_browser(cfg)

            keywords = cfg.get("keywords") or []
            urls = cfg.get("urls") or []
            platforms = cfg.get("platforms") or []

            # 总任务数估算：仅用于进度条
            total_tasks = max(1, len(platforms) * (len(keywords) + len(urls)))
            done = 0

            for plat in platforms:
                if self._stop:
                    break
                cls = SCRAPER_REGISTRY.get(plat)
                if not cls:
                    self.log.emit("WARN", f"未知平台：{plat}")
                    continue
                scraper = cls(browser, cfg)

                # URL 直采
                for url in urls:
                    if self._stop:
                        break
                    if not self._url_match(url, plat):
                        continue
                    try:
                        prod = scraper.parse_url(url)
                        if prod:
                            results.append(prod)
                            self.product_done.emit(prod)
                    except Exception as exc:  # noqa: BLE001
                        self.log.emit("WARN", f"URL 解析失败 {url}: {exc}")
                    sleep_random(cfg["browser"]["request_interval"])
                    done += 1
                    self.progress.emit(done, total_tasks, f"[{plat}] URL")

                # 关键词搜索
                for kw in keywords:
                    if self._stop:
                        break
                    self.log.emit("INFO", f"[{plat}] 搜索关键词：{kw}")
                    try:
                        products = scraper.search(
                            kw,
                            max_pages=cfg["max_pages"],
                            limit=cfg["per_keyword_limit"],
                        )
                    except Exception as exc:  # noqa: BLE001
                        self.log.emit("ERROR", f"[{plat}] 搜索失败：{exc}")
                        continue

                    sub_total = max(1, len(products))
                    for i, p in enumerate(products, 1):
                        if self._stop:
                            break
                        try:
                            scraper.fetch_detail(p)
                        except Exception as exc:  # noqa: BLE001
                            self.log.emit("WARN", f"详情失败 {p.url}: {exc}")
                        # 单条分类后立即上抛 UI
                        classify_products(
                            [p], cfg["type_rules"], cfg["price_buckets"]
                        )
                        results.append(p)
                        self.product_done.emit(p)
                        self.progress.emit(
                            done, total_tasks,
                            f"[{plat}] {kw} {i}/{sub_total}"
                        )
                        sleep_random(cfg["browser"]["request_interval"])
                    done += 1

            if self._stop:
                self.log.emit("WARN", "用户已中止抓取。")
            self.finished_ok.emit(results)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
        finally:
            if browser is not None:
                try:
                    browser.quit()
                except Exception:  # noqa: BLE001
                    pass

    # ----------- 辅助 -----------
    def _build_browser(self, cfg: dict):
        # 延迟导入，启动时再初始化
        from DrissionPage import ChromiumOptions, ChromiumPage

        opts = ChromiumOptions()
        opts.set_user_data_path(cfg["browser"].get("user_data_dir", ".browser_profile"))
        if cfg["browser"].get("headless"):
            opts.headless()
        opts.set_argument("--disable-blink-features=AutomationControlled")
        opts.set_argument("--lang=zh-CN")
        return ChromiumPage(opts)

    @staticmethod
    def _url_match(url: str, platform: str) -> bool:
        if platform == "alibaba1688":
            return "1688.com" in url
        if platform == "pinduoduo":
            return "yangkeduo.com" in url or "pinduoduo.com" in url
        return False
