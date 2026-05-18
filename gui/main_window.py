"""
主窗口：左侧导航 + 右侧堆叠页面
"""
from __future__ import annotations
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QStackedWidget, QLabel, QMessageBox, QInputDialog, QLineEdit,
)

from .theme import QSS, COLORS
from .pages.dashboard_page import DashboardPage
from .pages.functions_page import FunctionsPage
from .pages.wallets_page import WalletsPage
from .pages.api_page import ApiPage
from .pages.logs_page import LogsPage
from .pages.arbitrage_page import ArbitragePage
from .log_bridge import LogBridge
from .runner import StrategyRunner

from core.config import load_config, reload_from_vault
from core.vault import Vault
from core.logger import logger


NAV_ITEMS = [
    ("dashboard",  "◉  仪表盘",   "实时监控"),
    ("functions",  "⚡  功能",     "启停策略"),
    ("arbitrage",  "💱  套利",     "CEX-DEX 套利"),
    ("wallets",    "🔑  钱包",     "私钥管理"),
    ("api",        "📡  API 设置", "RPC / 通知"),
    ("logs",       "📜  日志",     "实时日志流"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chain Sniper · Multi-Chain Alpha Framework")
        self.resize(1280, 820)
        self.setMinimumSize(1080, 700)

        # 核心依赖
        self.vault = Vault()
        self.cfg = load_config(self.vault)
        self.runner = StrategyRunner(self.cfg)
        self.runner.start_loop()

        # 持仓缓存（key: "fn_code:token"）
        self._positions: dict[str, dict] = {}

        self._build_ui()
        self._wire()

        # 日志桥
        self.log_bridge = LogBridge()
        self.log_bridge.message.connect(self.logs_page.append_log)

        logger.info("Chain Sniper GUI started")

        # 提示用户解锁（如果已初始化）
        if self.vault.is_initialized() and self.vault.is_locked():
            self._prompt_unlock_at_startup()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------- Sidebar ----------
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(0, 0, 0, 16)
        sb_lay.setSpacing(0)

        logo = QLabel("⚡ CHAIN SNIPER")
        logo.setObjectName("logo")
        sub = QLabel("ALPHA  ·  v0.1.0")
        sub.setObjectName("logoSub")
        sb_lay.addWidget(logo)
        sb_lay.addWidget(sub)

        self.nav_buttons: dict[str, QPushButton] = {}
        for key, text, _ in NAV_ITEMS:
            btn = QPushButton(text)
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, k=key: self._navigate(k))
            sb_lay.addWidget(btn)
            self.nav_buttons[key] = btn

        sb_lay.addStretch()

        quick_label = QLabel("  快捷操作")
        quick_label.setStyleSheet(f"color: {COLORS['text_mute']}; font-size: 11px; padding: 0 16px;")
        sb_lay.addWidget(quick_label)

        self.stop_all_btn = QPushButton("⏹  停止全部")
        self.stop_all_btn.setObjectName("stopBtn")
        self.stop_all_btn.clicked.connect(self._stop_all)
        self.stop_all_btn.setEnabled(False)
        stop_wrap = QHBoxLayout()
        stop_wrap.setContentsMargins(14, 6, 14, 6)
        stop_wrap.addWidget(self.stop_all_btn)
        sb_lay.addLayout(stop_wrap)

        root.addWidget(sidebar)

        # ---------- Main content ----------
        self.stack = QStackedWidget()
        self.dashboard_page = DashboardPage()
        self.functions_page = FunctionsPage()
        self.arbitrage_page = ArbitragePage()
        self.wallets_page = WalletsPage(self.vault)
        self.api_page = ApiPage(self.vault)
        self.logs_page = LogsPage()

        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.functions_page)
        self.stack.addWidget(self.arbitrage_page)
        self.stack.addWidget(self.wallets_page)
        self.stack.addWidget(self.api_page)
        self.stack.addWidget(self.logs_page)

        self._page_index = {
            "dashboard": 0, "functions": 1, "arbitrage": 2,
            "wallets": 3, "api": 4, "logs": 5,
        }

        root.addWidget(self.stack, 1)
        self._navigate("dashboard")

    def _wire(self) -> None:
        # 功能卡片 -> 启停
        self.functions_page.fn_toggled.connect(self._on_fn_toggle)
        # 套利页面 -> 启停
        self.arbitrage_page.arb_toggled.connect(self._on_fn_toggle)
        # Runner -> UI
        self.runner.fn_started.connect(self._on_fn_started)
        self.runner.fn_stopped.connect(self._on_fn_stopped)
        self.runner.fn_error.connect(self._on_fn_error)
        # SignalBus 数据流
        self.runner.signal_emitted.connect(self._on_bus_signal)
        self.runner.position_updated.connect(self._on_bus_position)
        self.runner.bus_log.connect(self._on_bus_log)
        # 配置保存 -> 刷新 runner 用的 cfg
        self.api_page.api_saved.connect(self._on_config_changed)
        self.api_page.api_saved.connect(self.wallets_page._refresh_lock_hint)
        self.api_page.api_saved.connect(self.wallets_page._refresh_table)
        self.wallets_page.wallets_changed.connect(self._on_config_changed)

    def _prompt_unlock_at_startup(self) -> None:
        pwd, ok = QInputDialog.getText(
            self, "解锁保险箱",
            "检测到已保存的配置。请输入主密码以加载 API Key 和钱包：",
            QLineEdit.Password,
        )
        if not ok or not pwd:
            return
        try:
            self.vault.unlock(pwd)
            self._on_config_changed()
            # 触发页面刷新
            self.api_page.refresh()
            self.wallets_page._refresh_lock_hint()
            self.wallets_page._refresh_table()
        except Exception as e:
            QMessageBox.warning(self, "解锁失败", str(e))

    # ---------- 导航 ----------

    def _navigate(self, key: str) -> None:
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)
        self.stack.setCurrentIndex(self._page_index[key])

    # ---------- 功能启停 ----------

    def _on_fn_toggle(self, fn_code: str, should_run: bool) -> None:
        if should_run:
            # 启动前确认钱包/配置
            if not self.vault.is_locked() and not self._warm_check(fn_code):
                # 用户可以继续（仅提示），dry_run 默认打开
                pass
            self.runner.start_fn(fn_code, dry_run=True)
        else:
            self.runner.stop_fn(fn_code)

    def _warm_check(self, fn_code: str) -> bool:
        """启动前检查：是否有对应链的钱包、RPC 是否设置"""
        from functions import REGISTRY
        chain = REGISTRY[fn_code]["chain"]
        if self.vault.is_locked():
            return True
        if not self.vault.get_private_key(chain):
            QMessageBox.information(
                self, "提示",
                f"未配置 {chain} 钱包。将以 DRY_RUN 模式运行（不下单，仅检测）。\n"
                f"如需实盘，请先到『钱包』页面导入私钥。",
            )
        return True

    def _on_fn_started(self, fn_code: str) -> None:
        self.functions_page.set_running(fn_code, True)
        if "arb_cex_dex" in fn_code:
            self.arbitrage_page.set_running(fn_code, True)
        running = self.runner.running_set()
        self.dashboard_page.update_running_count(running)
        self.stop_all_btn.setEnabled(len(running) > 0)

    def _on_fn_stopped(self, fn_code: str) -> None:
        self.functions_page.set_running(fn_code, False)
        if "arb_cex_dex" in fn_code:
            self.arbitrage_page.set_running(fn_code, False)
        running = self.runner.running_set()
        self.dashboard_page.update_running_count(running)
        self.stop_all_btn.setEnabled(len(running) > 0)

    def _on_fn_error(self, fn_code: str, err: str) -> None:
        QMessageBox.warning(self, f"{fn_code} 出错", err[:500])
        self.logs_page.append_log("ERROR", f"{fn_code}: {err}")

    def _stop_all(self) -> None:
        for fn_code in list(self.runner.running_set()):
            self.runner.stop_fn(fn_code)

    # ---------- Bus 事件 -> Dashboard ----------

    def _on_bus_signal(self, fn_code: str, token: str, action: str,
                       amount: float, note: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.dashboard_page.push_signal(ts, token, action, amount, f"[{fn_code}] {note}")

    def _on_bus_position(self, fn_code: str, token: str,
                         entry: float, current: float, size: float) -> None:
        key = f"{fn_code}:{token}"
        self._positions[key] = {
            "token": token, "entry": entry, "current": current, "size_usd": size,
        }
        self.dashboard_page.update_positions(list(self._positions.values()))

    def _on_bus_log(self, fn_code: str, level: str, msg: str) -> None:
        self.logs_page.append_log(level, f"[{fn_code}] {msg}")

    # ---------- 配置刷新 ----------

    def _on_config_changed(self) -> None:
        """用户保存了 API Key 或钱包，刷新 runner 的 cfg"""
        reload_from_vault(self.cfg, self.vault)
        self.runner.update_cfg(self.cfg)
        logger.info("config reloaded from vault")

    # ---------- 生命周期 ----------

    def closeEvent(self, event) -> None:
        self.runner.stop_loop()
        self.log_bridge.detach()
        super().closeEvent(event)
