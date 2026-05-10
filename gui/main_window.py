"""
主窗口：左侧导航 + 右侧堆叠页面 + 全局热键
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
from .pages.trenches_page import TrenchesPage
from .pages.functions_page import FunctionsPage
from .pages.wallets_page import WalletsPage
from .pages.api_page import ApiPage
from .pages.logs_page import LogsPage
from .pages.upcoming_page import UpcomingPage
from .log_bridge import LogBridge
from .runner import StrategyRunner
from .hotkeys import HotkeyManager

from core.config import load_config, reload_from_vault
from core.vault import Vault
from core.logger import logger


NAV_ITEMS = [
    ("dashboard",  "◉   仪表盘",      "Dashboard"),
    ("trenches",   "🎯  Trenches",   "实时发现"),
    ("upcoming",   "🚀  打新活动",    "Launchpads"),
    ("functions",  "⚡  策略",        "Strategies"),
    ("wallets",    "🔑  钱包",        "Wallets"),
    ("api",        "📡  API",         "RPC / 通知"),
    ("logs",       "📜  日志",        "Live Logs"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chain Sniper · Multi-Chain Trading Terminal")
        self.resize(1440, 900)
        self.setMinimumSize(1200, 760)

        # 核心依赖
        self.vault = Vault()
        self.cfg = load_config(self.vault)
        self.runner = StrategyRunner(self.cfg)
        self.runner.start_loop()

        # 持仓缓存
        self._positions: dict[str, dict] = {}
        self._latest_mint = None  # 最新信号的 mint，供热键使用

        self._build_ui()
        self._wire()
        self._setup_hotkeys()

        # 日志桥
        self.log_bridge = LogBridge()
        self.log_bridge.message.connect(self.logs_page.append_log)

        logger.info("Chain Sniper GUI started")

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
        sidebar.setFixedWidth(200)
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(0, 0, 0, 16)
        sb_lay.setSpacing(0)

        logo = QLabel("⚡ CHAIN SNIPER")
        logo.setObjectName("logo")
        sub = QLabel("PRO  ·  v0.3.0")
        sub.setObjectName("logoSub")
        sb_lay.addWidget(logo)
        sb_lay.addWidget(sub)

        self.nav_buttons: dict[str, QPushButton] = {}
        for key, text, _ in NAV_ITEMS:
            btn = QPushButton(text)
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._navigate(k))
            sb_lay.addWidget(btn)
            self.nav_buttons[key] = btn

        sb_lay.addStretch()

        # 热键提示
        hk_label = QLabel("  快捷键")
        hk_label.setStyleSheet(
            f"color: {COLORS['text_mute']}; font-size: 10px; "
            f"padding: 8px 20px 4px 20px; letter-spacing: 1.5px; font-weight: 600;"
        )
        sb_lay.addWidget(hk_label)

        for txt in ["F1-F4  金额档位", "Ctrl+B  狙击最新", "Esc     停止全部"]:
            lbl = QLabel(f"  {txt}")
            lbl.setStyleSheet(
                f"color: {COLORS['text_dim']}; font-size: 10px; "
                f"padding: 2px 20px; font-family: 'Cascadia Mono', monospace;"
            )
            sb_lay.addWidget(lbl)

        sb_lay.addSpacing(14)

        # 停止全部大按钮
        self.stop_all_btn = QPushButton("⏹  STOP ALL")
        self.stop_all_btn.setObjectName("stopBtn")
        self.stop_all_btn.setCursor(Qt.PointingHandCursor)
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
        self.trenches_page = TrenchesPage(self.runner)
        self.upcoming_page = UpcomingPage(self.runner)
        self.functions_page = FunctionsPage()
        self.wallets_page = WalletsPage(self.vault)
        self.api_page = ApiPage(self.vault)
        self.logs_page = LogsPage()

        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.trenches_page)
        self.stack.addWidget(self.upcoming_page)
        self.stack.addWidget(self.functions_page)
        self.stack.addWidget(self.wallets_page)
        self.stack.addWidget(self.api_page)
        self.stack.addWidget(self.logs_page)

        self._page_index = {
            "dashboard": 0, "trenches": 1, "upcoming": 2,
            "functions": 3, "wallets": 4, "api": 5, "logs": 6,
        }

        root.addWidget(self.stack, 1)
        self._navigate("dashboard")

    def _wire(self) -> None:
        # 功能启停
        self.functions_page.fn_toggled.connect(self._on_fn_toggle)

        # Runner 事件
        self.runner.fn_started.connect(self._on_fn_started)
        self.runner.fn_stopped.connect(self._on_fn_stopped)
        self.runner.fn_error.connect(self._on_fn_error)
        self.runner.signal_emitted.connect(self._on_bus_signal)
        self.runner.position_updated.connect(self._on_bus_position)
        self.runner.bus_log.connect(self._on_bus_log)

        # Quick Snipe (dashboard)
        self.dashboard_page.quick_buy_requested.connect(self._on_quick_buy)

        # Trenches 买卖
        self.trenches_page.buy_requested.connect(self._on_quick_buy)
        self.trenches_page.sell_requested.connect(self._on_quick_sell)

        # 配置刷新
        self.api_page.api_saved.connect(self._on_config_changed)
        self.api_page.api_saved.connect(self.wallets_page._refresh_lock_hint)
        self.api_page.api_saved.connect(self.wallets_page._refresh_table)
        self.wallets_page.wallets_changed.connect(self._on_config_changed)

    def _setup_hotkeys(self) -> None:
        self.hotkeys = HotkeyManager(self)
        self.hotkeys.stop_all.connect(self._stop_all)
        self.hotkeys.quick_buy_latest.connect(self._hotkey_buy_latest)
        self.hotkeys.preset_amount_triggered.connect(self._hotkey_preset)

    # ---------- 导航 ----------

    def _navigate(self, key: str) -> None:
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)
        self.stack.setCurrentIndex(self._page_index[key])

    # ---------- 解锁 ----------

    def _prompt_unlock_at_startup(self) -> None:
        pwd, ok = QInputDialog.getText(
            self, "解锁保险箱",
            "检测到已保存的配置。\n请输入主密码以加载 API Key 和钱包：",
            QLineEdit.Password,
        )
        if not ok or not pwd:
            return
        try:
            self.vault.unlock(pwd)
            self._on_config_changed()
            self.api_page.refresh()
            self.wallets_page._refresh_lock_hint()
            self.wallets_page._refresh_table()
        except Exception as e:
            QMessageBox.warning(self, "解锁失败", str(e))

    # ---------- 策略启停 ----------

    def _on_fn_toggle(self, fn_code: str, should_run: bool) -> None:
        if should_run:
            self.runner.start_fn(fn_code, dry_run=True)
            self.logs_page.append_log("INFO", f"▶ 启动 {fn_code}... 正在连接 RPC")
        else:
            self.runner.stop_fn(fn_code)
            self.logs_page.append_log("WARNING", f"■ 停止 {fn_code}")

    def _on_fn_started(self, fn_code: str) -> None:
        self.functions_page.set_running(fn_code, True)
        running = self.runner.running_set()
        self.dashboard_page.update_running_count(running)
        self.stop_all_btn.setEnabled(len(running) > 0)
        self.logs_page.append_log("SUCCESS", f"✓ {fn_code} 已启动，正在监听")

    def _on_fn_stopped(self, fn_code: str) -> None:
        self.functions_page.set_running(fn_code, False)
        running = self.runner.running_set()
        self.dashboard_page.update_running_count(running)
        self.stop_all_btn.setEnabled(len(running) > 0)

    def _on_fn_error(self, fn_code: str, err: str) -> None:
        QMessageBox.warning(self, f"{fn_code} 出错", err[:500])
        self.logs_page.append_log("ERROR", f"{fn_code}: {err}")

    def _stop_all(self) -> None:
        for fn_code in list(self.runner.running_set()):
            self.runner.stop_fn(fn_code)
        self.logs_page.append_log("WARNING", "⏹ 已停止所有策略")

    # ---------- Quick Buy / Sell ----------

    def _on_quick_buy(self, chain: str, mint: str, amount: float, slippage_bps: int) -> None:
        """用户从任何面板触发的一键买入"""
        # 检查钱包
        if not self.vault.is_locked():
            pk = self.vault.get_private_key(chain)
            if not pk:
                ret = QMessageBox.question(
                    self, "未配置钱包",
                    f"{chain} 链没有配置钱包私钥。\n\n"
                    f"要仅以 DRY_RUN 模式执行（不真实下单）吗？",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if ret != QMessageBox.Yes:
                    return

        self.logs_page.append_log(
            "INFO", f"⚡ 手动买入 {chain}: {mint[:12]}... amount={amount} slip={slippage_bps/100}%"
        )
        self.dashboard_page.push_signal(
            datetime.now().strftime("%H:%M:%S"),
            chain, mint[:8] + "...", "BUY", amount * 100,  # 粗略估算 USD
            f"manual buy · slip {slippage_bps/100}%",
            mint=mint,
        )

        # 通过 runner 在 asyncio loop 中执行
        self.runner.manual_trade(chain, mint, "buy", amount, slippage_bps)

    def _on_quick_sell(self, chain: str, mint: str, percent: int, slippage_bps: int) -> None:
        self.logs_page.append_log(
            "INFO", f"⚡ 卖出 {chain}: {mint[:12]}... {percent}%"
        )
        self.runner.manual_trade(chain, mint, "sell", percent, slippage_bps)

    # ---------- SignalBus → UI ----------

    def _on_bus_signal(self, fn_code: str, token: str, action: str,
                       amount: float, note: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        from functions import REGISTRY
        chain = REGISTRY.get(fn_code, {}).get("chain", "?")
        self.dashboard_page.push_signal(ts, chain, token, action, amount, f"[{fn_code}] {note}")
        self._latest_mint = (chain, token)

    def _on_bus_position(self, fn_code: str, token: str,
                         entry: float, current: float, size: float) -> None:
        key = f"{fn_code}:{token}"
        from functions import REGISTRY
        chain = REGISTRY.get(fn_code, {}).get("chain", "solana")
        self._positions[key] = {
            "token": token, "entry": entry, "current": current,
            "size_usd": size, "chain": chain, "mint": token,
        }
        self.dashboard_page.update_positions(list(self._positions.values()))

    def _on_bus_log(self, fn_code: str, level: str, msg: str) -> None:
        self.logs_page.append_log(level, f"[{fn_code}] {msg}")

    # ---------- 热键 ----------

    def _hotkey_buy_latest(self) -> None:
        if not self._latest_mint:
            self.logs_page.append_log("WARNING", "⚡ 没有最新信号可用")
            return
        chain, mint = self._latest_mint
        self._on_quick_buy(chain, mint, 0.1, 500)

    def _hotkey_preset(self, idx: int) -> None:
        # 往 quick snipe 面板的金额填默认档位
        presets = [0.1, 0.5, 1.0, 5.0]
        if 0 <= idx < len(presets):
            self.dashboard_page.quick_snipe.amount_input.setText(str(presets[idx]))
            self.logs_page.append_log(
                "INFO", f"F{idx+1}: 金额已设为 {presets[idx]}"
            )

    # ---------- 配置 ----------

    def _on_config_changed(self) -> None:
        reload_from_vault(self.cfg, self.vault)
        self.runner.update_cfg(self.cfg)
        logger.info("config reloaded from vault")

    # ---------- 生命周期 ----------

    def closeEvent(self, event) -> None:
        self.runner.stop_loop()
        self.log_bridge.detach()
        super().closeEvent(event)
