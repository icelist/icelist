"""后台抓取线程：每个平台一个独立 Tab，并行打开供用户登录."""
from __future__ import annotations

from PySide6.QtCore import QMutex, QThread, QWaitCondition, Signal

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
    """跑抓取的后台线程，并实现 Controller 协议。"""

    log = Signal(str, str)
    progress = Signal(int, int, str)
    product_done = Signal(object)
    finished_ok = Signal(list)
    failed = Signal(str)
    user_login_required = Signal(str, str)   # platform_name, message

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._stop = False
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._user_response: str | None = None  # "proceed" | "cancel"

    # ============== Controller 协议 ==============
    def is_stopping(self) -> bool:
        return self._stop

    def request_user_login(self, platform: str, message: str) -> bool:
        """从 scraper 线程调用。阻塞，直到 GUI 调用 proceed_login() 或 cancel_login()。"""
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
            self.log.emit("INFO", "正在启动浏览器...")
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

            # ===== 第一步：为每个平台开一个独立 Tab =====
            self.log.emit("INFO", f"打开 {len(platforms)} 个浏览器标签页（每个平台一个）...")
            tabs: dict[str, object] = {}      # platform -> tab
            scrapers: dict[str, object] = {}  # platform -> scraper

            first_tab = browser.latest_tab
            for i, plat in enumerate(platforms):
                cls = SCRAPER_REGISTRY.get(plat)
                if not cls:
                    continue
                if i == 0:
                    tab = first_tab
                else:
                    tab = browser.new_tab()
                tabs[plat] = tab
                scrapers[plat] = cls(browser, cfg, controller=self)
                # 绑定 tab 到 scraper（覆盖默认 latest_tab 行为）
                scrapers[plat]._tab = tab  # type: ignore[attr-defined]

                zh = scrapers[plat]._zh_name()  # type: ignore[attr-defined]
                self.log.emit("INFO", f"打开 {zh} 首页...")
                try:
                    tab.get(scrapers[plat].home_url,  # type: ignore[attr-defined]
                            timeout=cfg["browser"].get("page_load_timeout", 30))
                except Exception as exc:
                    self.log.emit("WARN", f"{zh} 首页加载失败：{exc}")
                sleep_random([0.6, 1.2])

            if self._stop:
                self.finished_ok.emit(results); return

            # ===== 第二步：并行确认登录 =====
            self.log.emit("INFO", "请检查每个平台的登录状态。如果未登录，按对话框提示完成登录。")
            for plat in platforms:
                if self._stop:
                    break
                scraper = scrapers.get(plat)
                tab = tabs.get(plat)
                if not scraper or not tab:
                    continue
                # 切到对应 tab，让用户在浏览器里也看到对应页面
                try:
                    tab.set.activate()
                except Exception:
                    pass
                if not scraper.ensure_logged_in(tab, target_url=scraper.home_url):  # type: ignore[attr-defined]
                    self.log.emit(
                        "WARN",
                        f"{scraper._zh_name()} 登录未完成或被取消，将跳过该平台。",  # type: ignore[attr-defined]
                    )
                    scrapers[plat] = None  # type: ignore[assignment]

            if self._stop:
                self.finished_ok.emit(results); return

            # ===== 第三步：按用户的关键词抓取 =====
            active_platforms = [p for p in platforms if scrapers.get(p)]
            if not active_platforms:
                self.failed.emit("没有可用的平台（全部跳过或登录失败）。")
                return

            self.log.emit("INFO", f"开始按关键词 {keywords} 抓取 {active_platforms}")
            total_tasks = max(1, len(active_platforms) * (len(keywords) + len(urls)))
            done = 0

            for plat in active_platforms:
                if self._stop:
                    break
                scraper = scrapers[plat]
                tab = tabs[plat]
                # 让 scraper 始终用绑定的 tab
                # （通过 monkey-patch search/fetch_detail 内部使用的 latest_tab）
                self._bind_tab(browser, tab)

                zh = scraper._zh_name()  # type: ignore[attr-defined]

                # URL 直采
                for url in urls:
                    if self._stop:
                        break
                    if not self._url_match(url, plat):
                        continue
                    try:
                        prod = scraper.parse_url(url)  # type: ignore[attr-defined]
                        if prod:
                            classify_products([prod], cfg["type_rules"], cfg["price_buckets"])
                            results.append(prod)
                            self.product_done.emit(prod)
                    except Exception as exc:
                        self.log.emit("WARN", f"URL 解析失败 {url}: {exc}")
                    sleep_random(cfg["browser"]["request_interval"])
                    done += 1
                    self.progress.emit(done, total_tasks, f"[{zh}] URL")

                # 关键词搜索（按用户填写的关键词逐个抓）
                for kw in keywords:
                    if self._stop:
                        break
                    self.log.emit("INFO", f"[{zh}] 搜索关键词：{kw}")
                    try:
                        products = scraper.search(  # type: ignore[attr-defined]
                            kw,
                            max_pages=cfg["max_pages"],
                            limit=cfg["per_keyword_limit"],
                        )
                    except Exception as exc:
                        self.log.emit("ERROR", f"[{zh}] 搜索 '{kw}' 失败：{exc}")
                        done += 1
                        continue

                    self.log.emit("INFO", f"[{zh}] '{kw}' 列表抓到 {len(products)} 件，开始抓详情...")
                    sub_total = max(1, len(products))
                    for i, p in enumerate(products, 1):
                        if self._stop:
                            break
                        try:
                            scraper.fetch_detail(p)  # type: ignore[attr-defined]
                        except Exception as exc:
                            self.log.emit("WARN", f"详情失败 {p.url}: {exc}")
                        classify_products([p], cfg["type_rules"], cfg["price_buckets"])
                        results.append(p)
                        self.product_done.emit(p)
                        self.progress.emit(
                            done, total_tasks,
                            f"[{zh}] {kw} {i}/{sub_total}"
                        )
                        sleep_random(cfg["browser"]["request_interval"])
                    done += 1

            if self._stop:
                self.log.emit("WARN", "用户已中止抓取。")
            self.log.emit("INFO", f"抓取流程结束，共 {len(results)} 件商品。")
            self.finished_ok.emit(results)
        except Exception as exc:
            self.failed.emit(f"{exc}")
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
    def _bind_tab(browser, tab) -> None:
        """切换浏览器 latest_tab 为目标 tab（让默认调用走对的 tab）。"""
        try:
            tab.set.activate()
        except Exception:
            pass

    @staticmethod
    def _url_match(url: str, platform: str) -> bool:
        if platform == "alibaba1688":
            return "1688.com" in url
        if platform == "pinduoduo":
            return "yangkeduo.com" in url or "pinduoduo.com" in url
        return False
