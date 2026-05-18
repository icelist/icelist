"""
Arbitrage 页面 —— CEX-DEX 套利机器人控制面板

功能：
  - 实时显示各交易对的 CEX/DEX 价差
  - 套利机会列表（自动刷新）
  - 执行历史记录
  - 参数配置（最小价差、最大金额等）
  - 一键启停
"""
from __future__ import annotations
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QGridLayout, QPushButton, QComboBox, QDoubleSpinBox,
    QSpinBox, QGroupBox, QFormLayout, QTabWidget, QScrollArea,
)

from ..theme import COLORS
from ..widgets.cards import StatCard, Card


class ArbitragePage(QWidget):
    """CEX-DEX 套利控制面板"""

    arb_toggled = Signal(str, bool)  # fn_code, should_run
    config_changed = Signal(dict)    # 新配置

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running: dict[str, bool] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(16)

        # 标题
        title = QLabel("CEX-DEX 套利")
        title.setObjectName("pageTitle")
        subtitle = QLabel("监控链上 (DEX) 与交易所 (CEX) 之间的价差，自动执行套利交易")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        # 统计卡片行
        stats_row = QGridLayout()
        stats_row.setSpacing(12)
        self.card_spread = StatCard("最大价差", "0.00%", COLORS["accent"])
        self.card_opportunities = StatCard("发现机会", "0", COLORS["text_bright"])
        self.card_executed = StatCard("已执行", "0", COLORS["text_bright"])
        self.card_profit = StatCard("累计利润", "$0.00", COLORS["success"])
        stats_row.addWidget(self.card_spread, 0, 0)
        stats_row.addWidget(self.card_opportunities, 0, 1)
        stats_row.addWidget(self.card_executed, 0, 2)
        stats_row.addWidget(self.card_profit, 0, 3)
        root.addLayout(stats_row)

        # Tab: 实时价差 / 执行历史 / 设置
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._build_spread_tab(), "📊  实时价差")
        tabs.addTab(self._build_history_tab(), "📜  执行历史")
        tabs.addTab(self._build_settings_tab(), "⚙  参数设置")
        root.addWidget(tabs, 1)

        # 底部控制栏
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(12)

        self.chain_combo = QComboBox()
        self.chain_combo.addItems(["Ethereum", "BSC", "Solana"])
        self.chain_combo.setMinimumWidth(130)
        ctrl_row.addWidget(QLabel("链:"))
        ctrl_row.addWidget(self.chain_combo)

        ctrl_row.addStretch()

        self.btn_start = QPushButton("▶  启动套利")
        self.btn_start.setObjectName("startArbBtn")
        self.btn_start.setMinimumWidth(140)
        self.btn_start.clicked.connect(self._on_start_clicked)

        self.btn_stop = QPushButton("⏹  停止")
        self.btn_stop.setObjectName("stopBtn")
        self.btn_stop.setMinimumWidth(100)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop_clicked)

        ctrl_row.addWidget(self.btn_start)
        ctrl_row.addWidget(self.btn_stop)
        root.addLayout(ctrl_row)

    # ---------- Tab: 实时价差 ----------

    def _build_spread_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 12, 8, 8)

        self.spread_table = QTableWidget(0, 7)
        self.spread_table.setHorizontalHeaderLabels([
            "交易对", "CEX 买一", "CEX 卖一", "DEX 买入价", "DEX 卖出价", "价差 %", "状态"
        ])
        self.spread_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.spread_table.verticalHeader().setVisible(False)
        self.spread_table.setAlternatingRowColors(True)
        self.spread_table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.spread_table)
        return w

    # ---------- Tab: 执行历史 ----------

    def _build_history_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 12, 8, 8)

        self.history_table = QTableWidget(0, 7)
        self.history_table.setHorizontalHeaderLabels([
            "时间", "交易对", "方向", "金额", "利润", "耗时", "结果"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.history_table)
        return w

    # ---------- Tab: 设置 ----------

    def _build_settings_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 16, 12, 16)
        lay.setSpacing(16)

        # 基础参数
        basic_group = QGroupBox("基础参数")
        basic_form = QFormLayout(basic_group)

        self.spin_min_spread = QDoubleSpinBox()
        self.spin_min_spread.setRange(0.01, 10.0)
        self.spin_min_spread.setValue(0.3)
        self.spin_min_spread.setSuffix(" %")
        self.spin_min_spread.setDecimals(2)
        basic_form.addRow("最小价差阈值:", self.spin_min_spread)

        self.spin_min_profit = QDoubleSpinBox()
        self.spin_min_profit.setRange(0.1, 100.0)
        self.spin_min_profit.setValue(2.0)
        self.spin_min_profit.setPrefix("$ ")
        self.spin_min_profit.setDecimals(2)
        basic_form.addRow("最小净利润:", self.spin_min_profit)

        self.spin_max_trade = QDoubleSpinBox()
        self.spin_max_trade.setRange(10, 10000)
        self.spin_max_trade.setValue(500)
        self.spin_max_trade.setPrefix("$ ")
        self.spin_max_trade.setDecimals(0)
        basic_form.addRow("单次最大金额:", self.spin_max_trade)

        self.spin_min_trade = QDoubleSpinBox()
        self.spin_min_trade.setRange(5, 1000)
        self.spin_min_trade.setValue(50)
        self.spin_min_trade.setPrefix("$ ")
        self.spin_min_trade.setDecimals(0)
        basic_form.addRow("单次最小金额:", self.spin_min_trade)

        lay.addWidget(basic_group)

        # 费率参数
        fee_group = QGroupBox("费率 & 风控")
        fee_form = QFormLayout(fee_group)

        self.spin_cex_fee = QDoubleSpinBox()
        self.spin_cex_fee.setRange(0.0, 1.0)
        self.spin_cex_fee.setValue(0.1)
        self.spin_cex_fee.setSuffix(" %")
        self.spin_cex_fee.setDecimals(3)
        fee_form.addRow("CEX 手续费:", self.spin_cex_fee)

        self.spin_slippage = QDoubleSpinBox()
        self.spin_slippage.setRange(0.0, 5.0)
        self.spin_slippage.setValue(0.3)
        self.spin_slippage.setSuffix(" %")
        self.spin_slippage.setDecimals(2)
        fee_form.addRow("DEX 滑点预估:", self.spin_slippage)

        self.spin_max_gas = QSpinBox()
        self.spin_max_gas.setRange(1, 500)
        self.spin_max_gas.setValue(50)
        self.spin_max_gas.setSuffix(" Gwei")
        fee_form.addRow("最大 Gas 价格:", self.spin_max_gas)

        self.spin_concurrent = QSpinBox()
        self.spin_concurrent.setRange(1, 10)
        self.spin_concurrent.setValue(3)
        fee_form.addRow("最大并发套利:", self.spin_concurrent)

        self.spin_cooldown = QSpinBox()
        self.spin_cooldown.setRange(1, 300)
        self.spin_cooldown.setValue(10)
        self.spin_cooldown.setSuffix(" 秒")
        fee_form.addRow("冷却时间:", self.spin_cooldown)

        lay.addWidget(fee_group)

        # 执行模式
        mode_group = QGroupBox("执行模式")
        mode_form = QFormLayout(mode_group)

        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["atomic (原子模式 - 更安全)", "parallel (并行模式 - 更快)"])
        mode_form.addRow("模式:", self.combo_mode)

        self.spin_scan_interval = QDoubleSpinBox()
        self.spin_scan_interval.setRange(0.5, 30.0)
        self.spin_scan_interval.setValue(2.0)
        self.spin_scan_interval.setSuffix(" 秒")
        self.spin_scan_interval.setDecimals(1)
        mode_form.addRow("扫描间隔:", self.spin_scan_interval)

        lay.addWidget(mode_group)

        # 保存按钮
        save_btn = QPushButton("💾  保存设置")
        save_btn.setObjectName("navBtn")
        save_btn.clicked.connect(self._save_settings)
        lay.addWidget(save_btn, alignment=Qt.AlignRight)

        lay.addStretch()
        scroll.setWidget(w)
        return scroll

    # ---------- 事件处理 ----------

    def _on_start_clicked(self) -> None:
        chain_map = {0: "eth", 1: "bsc", 2: "sol"}
        chain_prefix = chain_map.get(self.chain_combo.currentIndex(), "eth")
        fn_code = f"{chain_prefix}.arb_cex_dex"
        self.arb_toggled.emit(fn_code, True)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def _on_stop_clicked(self) -> None:
        chain_map = {0: "eth", 1: "bsc", 2: "sol"}
        chain_prefix = chain_map.get(self.chain_combo.currentIndex(), "eth")
        fn_code = f"{chain_prefix}.arb_cex_dex"
        self.arb_toggled.emit(fn_code, False)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _save_settings(self) -> None:
        """收集设置并发出信号"""
        settings = {
            "min_spread_pct": self.spin_min_spread.value(),
            "min_profit_usd": self.spin_min_profit.value(),
            "max_trade_usd": self.spin_max_trade.value(),
            "min_trade_usd": self.spin_min_trade.value(),
            "cex_fee_rate": self.spin_cex_fee.value() / 100,
            "dex_slippage_pct": self.spin_slippage.value(),
            "max_gas_gwei": self.spin_max_gas.value(),
            "max_concurrent": self.spin_concurrent.value(),
            "cooldown_seconds": self.spin_cooldown.value(),
            "execution_mode": "atomic" if self.combo_mode.currentIndex() == 0 else "parallel",
            "scan_interval": self.spin_scan_interval.value(),
        }
        self.config_changed.emit(settings)

    # ---------- 外部更新接口 ----------

    def set_running(self, fn_code: str, running: bool) -> None:
        self._running[fn_code] = running
        any_running = any(self._running.values())
        self.btn_start.setEnabled(not any_running)
        self.btn_stop.setEnabled(any_running)

    def update_spread(self, pair: str, cex_bid: float, cex_ask: float,
                      dex_bid: float, dex_ask: float, spread_pct: float) -> None:
        """更新价差表"""
        # 查找已有行或新建
        row = -1
        for r in range(self.spread_table.rowCount()):
            item = self.spread_table.item(r, 0)
            if item and item.text() == pair:
                row = r
                break
        if row == -1:
            row = self.spread_table.rowCount()
            self.spread_table.insertRow(row)

        items = [
            QTableWidgetItem(pair),
            QTableWidgetItem(f"${cex_bid:.4f}"),
            QTableWidgetItem(f"${cex_ask:.4f}"),
            QTableWidgetItem(f"${dex_bid:.4f}"),
            QTableWidgetItem(f"${dex_ask:.4f}"),
            QTableWidgetItem(f"{spread_pct:.3f}%"),
            QTableWidgetItem("监控中" if not any(self._running.values()) else "运行中"),
        ]

        # 价差着色
        spread_item = items[5]
        if spread_pct > 0.5:
            spread_item.setForeground(Qt.green)
        elif spread_pct > 0.2:
            spread_item.setForeground(Qt.yellow)
        else:
            spread_item.setForeground(Qt.gray)

        for col, it in enumerate(items):
            self.spread_table.setItem(row, col, it)

    def push_execution(self, time_str: str, pair: str, direction: str,
                       amount: float, profit: float, time_ms: float,
                       success: bool) -> None:
        """添加执行记录"""
        row = 0
        self.history_table.insertRow(row)
        result_text = "✅ 成功" if success else "❌ 失败"
        items = [
            QTableWidgetItem(time_str),
            QTableWidgetItem(pair),
            QTableWidgetItem(direction),
            QTableWidgetItem(f"${amount:.2f}"),
            QTableWidgetItem(f"${profit:.2f}"),
            QTableWidgetItem(f"{time_ms:.0f}ms"),
            QTableWidgetItem(result_text),
        ]
        if success:
            items[4].setForeground(Qt.green)
        else:
            items[4].setForeground(Qt.red)

        for col, it in enumerate(items):
            self.history_table.setItem(row, col, it)

        # 限制行数
        while self.history_table.rowCount() > 100:
            self.history_table.removeRow(self.history_table.rowCount() - 1)

    def update_stats(self, max_spread: float, opportunities: int,
                     executed: int, profit: float) -> None:
        """更新统计卡片"""
        self.card_spread.set_value(f"{max_spread:.2f}%",
                                   COLORS["accent"] if max_spread > 0.3 else COLORS["text_mute"])
        self.card_opportunities.set_value(str(opportunities), COLORS["text_bright"])
        self.card_executed.set_value(str(executed), COLORS["text_bright"])
        if profit >= 0:
            self.card_profit.set_value(f"+${profit:.2f}", COLORS["success"])
        else:
            self.card_profit.set_value(f"-${abs(profit):.2f}", COLORS["error"])
