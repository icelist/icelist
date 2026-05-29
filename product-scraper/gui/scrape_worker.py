"""后台抓取线程：每个平台一个独立 Tab；按需登录；详细进度日志."""
from __future__ import annotations

from PySide6.QtCore import QMutex, QThread, QWaitCondition, Signal
from loguru import logger

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
    log = Signal(str, str)
    progress = Signal(int, int, str)
    product_done = Signal(object)
    finished_ok = Signal(list)
    failed = Signal(str)
    user_login_required = Signal(str, str)

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._stop = False
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._user_response: str | None = None

    # ============== Controller 协议 ==============
    def is_stopping(self) -> bool:
        return self._stop

    def request_user_login(self, platform: str, message: str) -> bool:
        self.user_login_required.emit(platform, message)
        self._mutex.lock()
        try:
            self._user_response = None
            while self._user_response is None and not self._stop:
                self._cond.wait(self._mutex, 200)
            return self._user_response == "proceed"
        finally:
            self._user_response = None
            self._mutex.unlock()

    # ============== 来自 GUI ==============
    def proceed_login(self) -> None:
        self._mutex.lock()
        try:
            self._user_response = "proceed"
            self._cond.wakeAll()
        finally:
            self._mutex.unlock()

    def cancel_login(self) -> None:
        self._mutex.lock()
        try:
            self._user_response = "cancel"
            self._cond.wakeAll()
        finally:
            self._mutex.unlock()

    def stop(self) -> None:
        self._stop = True
        self._mutex.lock()
        try:
            self._user_response = "cancel"
            self._cond.wakeAll()
        finally:
            self._mutex.unlock()

    # ============== run ==============
    def run(self) -> None:  # noqa: C901
        cfg = self.cfg
        results: list[Product] = []
        browser = None
        try:
            logger.info("正在启动浏览器（首次启动需要 5~15 秒）...")
            try:
                browser = self._build_browser(cfg)
            except Exception as exc:
                self.failed.emit(f"启动浏览器失败：{exc}\n请确认本机已安装 Chrome 或 Edge。")
                return

            platforms = cfg.get("platforms") or []
            keywords = cfg.get("keywords") or []
            urls = cfg.get("urls") or []

            if not keywords and not urls:
                self.failed.emit("请至少填写一个关键词或 URL。")
                return

            # 给每个平台开独立 tab（不立刻去首页，避免与 search 双重导航）
            logger.info(f"打开 {len(platforms)} 个浏览器标签页...")
            tabs: dict = {}
            scrapers: dict = {}
            first_tab = browser.latest_tab
            for i, plat in enumerate(platforms):
                cls = SCRAPER_REGISTRY.get(plat)
                if not cls:
                    continue
                tab = first_tab if i == 0 else browser.new_tab()
                tabs[plat] = tab
                scrapers[plat] = cls(browser, cfg, controller=self)
                scrapers[plat]._tab = tab
                zh = scrapers[plat]._zh_name()
                logger.info(f"  Tab {i+1}: {zh}")

            if self._stop:
                self.finished_ok.emit(results); return

            # 总任务数（只算关键词，URL 直采单算）
            tasks_per_plat = max(1, len(keywords))
            total_tasks = max(1, len(platforms) * tasks_per_plat + len(platforms) * len(urls))
            done = 0

            # 直接进入抓取；search() 内部会按需触发登录对话框
            for plat in platforms:
                if self._stop:
                    break
                scraper = scrapers.get(plat)
                tab = tabs.get(plat)
                if not scraper or not tab:
                    continue
                # 切到本平台的 tab，让用户在浏览器看到对应 tab
                try:
                    tab.set.activate()
                except Exception:
                    pass

                zh = scraper._zh_name()

                # URL 直采
                for url in urls:
                    if self._stop:
                        break
                    if not self._url_match(url, plat):
                        continue
                    try:
                        prod = scraper.parse_url(url)
                        if prod:
                            classify_products([prod], cfg["type_rules"], cfg["price_buckets"])
                            results.append(prod)
                            self.product_done.emit(prod)
                    except Exception as exc:
                        logger.warning(f"URL 解析失败 {url}: {exc}")
                    sleep_random(cfg["browser"]["request_interval"])
                    done += 1
                    self.progress.emit(done, total_tasks, f"[{zh}] URL")

                # 关键词搜索
                for kw in keywords:
                    if self._stop:
                        break
                    logger.info(f"========== [{zh}] 开始搜索：{kw} ==========")
                    try:
                        products = scraper.search(
                            kw,
                            max_pages=cfg["max_pages"],
                            limit=cfg["per_keyword_limit"],
                        )
                    except Exception as exc:
                        logger.error(f"[{zh}] 搜索 '{kw}' 异常：{exc}")
                        done += 1
                        self.progress.emit(done, total_tasks, f"[{zh}] {kw} 失败")
                        continue

                    if not products:
                        logger.warning(
                            f"[{zh}] 关键词 '{kw}' 没抓到列表项。"
                            f"可能原因：1) 该平台仍未通过验证；2) 搜索结果为空；"
                            f"3) 页面结构变化。可在浏览器对应 Tab 里手动操作排查。"
                        )
                        done += 1
                        self.progress.emit(done, total_tasks, f"[{zh}] {kw} 0 件")
                        continue

                    logger.info(f"[{zh}] '{kw}' 列表 {len(products)} 件，开始抓详情...")
                    sub_total = len(products)
                    for i, p in enumerate(products, 1):
                        if self._stop:
                            break
                        try:
                            scraper.fetch_detail(p)
                        except Exception as exc:
                            logger.warning(f"详情失败 {p.url}: {exc}")
                        classify_products([p], cfg["type_rules"], cfg["price_buckets"])
                        results.append(p)
                        self.product_done.emit(p)
                        self.progress.emit(
                            done, total_tasks,
                            f"[{zh}] {kw} 详情 {i}/{sub_total}",
                        )
                        sleep_random(cfg["browser"]["request_interval"])
                    done += 1
                    self.progress.emit(done, total_tasks, f"[{zh}] {kw} 完成")

            if self._stop:
                logger.warning("用户已中止抓取。")
            logger.info(f"抓取流程结束，共 {len(results)} 件商品。")
            self.finished_ok.emit(results)
        except Exception as exc:
            logger.error(f"Worker 异常退出：{exc}")
            self.failed.emit(str(exc))
        finally:
            if browser is not None:
                try:
                    browser.quit()
                except Exception:
                    pass

    # ============== 辅助 ==============
    def _build_browser(self, cfg: dict):
        from DrissionPage import ChromiumOptions, ChromiumPage

        opts = ChromiumOptions()
        opts.set_user_data_path(cfg["browser"].get("user_data_dir", ".browser_profile"))
        if cfg["browser"].get("headless"):
            opts.headless()
        opts.set_argument("--disable-blink-features=AutomationControlled")
        opts.set_argument("--lang=zh-CN")
        opts.set_argument("--window-size=1280,900")
        return ChromiumPage(opts)

    @staticmethod
    def _url_match(url: str, platform: str) -> bool:
        if platform == "alibaba1688":
            return "1688.com" in url
        if platform == "pinduoduo":
            return "yangkeduo.com" in url or "pinduoduo.com" in url
        return False
