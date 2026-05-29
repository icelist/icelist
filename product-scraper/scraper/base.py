"""抓取器基类与商品数据模型."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Protocol


class Controller(Protocol):
    """抓取器和 GUI 工作线程通信用的协议（鸭子类型，避免循环 import）。"""

    def is_stopping(self) -> bool: ...
    def request_user_login(self, platform: str, message: str) -> bool: ...
    def log(self, level: str, msg: str) -> None: ...


@dataclass
class Product:
    platform: str
    product_id: str
    title: str
    url: str
    price: float | None = None
    price_text: str | None = None
    images: list[str] = field(default_factory=list)
    local_images: list[str] = field(default_factory=list)
    specs: dict[str, Any] = field(default_factory=dict)
    features: list[str] = field(default_factory=list)
    category_path: str | None = None
    shop: str | None = None
    sales: str | None = None
    keyword: str | None = None
    bucket_type: str | None = None
    bucket_price: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseScraper:
    """所有平台抓取器的基类。"""

    name: str = "base"
    home_url: str = ""

    def __init__(self, browser, config: dict, controller: Controller | None = None):
        self.browser = browser
        self.config = config
        self.controller = controller
        self._tab = None  # 由外部（worker）绑定到平台专属 tab

    @property
    def tab(self):
        """优先使用绑定的 tab；否则用 latest_tab。"""
        if self._tab is not None:
            return self._tab
        return self.browser.latest_tab

    # ---------- 子类需要实现 ----------
    def search(self, keyword: str, max_pages: int, limit: int) -> list[Product]:
        raise NotImplementedError

    def fetch_detail(self, product: Product) -> Product:
        raise NotImplementedError

    def parse_url(self, url: str) -> Product | None:
        raise NotImplementedError

    def is_login_page(self, page) -> bool:
        """子类可以覆盖以做更精确的检测；默认看 URL 和 HTML 关键词。"""
        url = (page.url or "").lower()
        if any(k in url for k in ("login", "passport", "captcha", "punish", "sec.x")):
            return True
        try:
            html = (page.html or "")[:3000]
        except Exception:
            html = ""
        keywords = ("请登录", "请完成", "请滑动", "拖动滑块", "验证身份", "扫码登录", "账号登录")
        return any(k in html for k in keywords)

    # ---------- 通用：登录等待 ----------
    def ensure_logged_in(self, page, target_url: str | None = None,
                         timeout_each_load: int = 30) -> bool:
        """
        最多重试 3 次：检测到登录页 → 让 controller 阻塞等用户 → 重新加载目标页。
        Returns True if logged in successfully, False if canceled or stop signaled.
        """
        for attempt in range(3):
            if self.controller and self.controller.is_stopping():
                return False
            if not self.is_login_page(page):
                return True
            if not self.controller:
                return False
            ok = self.controller.request_user_login(
                self.name,
                f"检测到【{self._zh_name()}】需要登录或滑块验证。\n\n"
                f"请在弹出的浏览器窗口中扫码或输入账号登录、或拖动滑块验证。\n"
                f"完成后点击下方按钮 ✅【已完成，继续抓取】。\n\n"
                f"提示：登录信息会自动记忆，下次启动免登。"
            )
            if not ok:
                return False
            # 用户点了"已完成"，回到目标页
            if target_url:
                try:
                    page.get(target_url, timeout=timeout_each_load)
                except Exception:
                    pass
            else:
                try:
                    page.refresh()
                except Exception:
                    pass
        return not self.is_login_page(page)

    def _zh_name(self) -> str:
        return {"alibaba1688": "1688", "pinduoduo": "拼多多"}.get(self.name, self.name)
