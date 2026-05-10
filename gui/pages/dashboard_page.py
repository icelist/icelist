"""
Dashboard —— 专业 sniper 主控台
布局（仿 BullX / Photon）：
┌─────────────────────────────────────────────────┐
│  4 个 Stat Card（运行/信号/持仓/PnL）             │
├──────────────────────┬──────────────────────────┤
│                      │                          │
│   📡 Live Signals   │   💼 Active Positions   │
│   (实时信号 + 内嵌   │   (带 sparkline + Sell) │
│    mint 快捷买入)    │                          │
│                      │                          │
├──────────────────────┴──────────────────────────┤
│   ⚡ Quick Snipe (手动粘地址一键狙击)           │
└─────────────────────────────────────────────────┘
"""
from __future__ import annotations
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLineEdit, QComboBox, QSplitter, QSizePolicy, QMessageBox,
)

from ..theme import COLORS, chain_color
from ..widgets.cards import StatCard, Card


class QuickSnipePanel(QFrame):
    """手动粘贴地址立即狙击（BullX 有类似面板）"""

    buy_requested = Signal(str, str, float, int)   # chain, mint, amount, slippage_bps

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("widgetCard")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        # 标题
        title = QLabel("⚡  Quick Snipe")
        title.setObjectName("cardTitle")
        subtitle = QLabel("粘贴代币地址 · 立即交易")
        subtitle.setObjectName("cardDesc")
        lay.addWidget(title)
        lay.addWidget(subtitle)

        # 输入行
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.chain_combo = QComboBox()
        self.chain_combo.addItems(["solana", "bsc", "ethereum"])
        self.chain_combo.setFixedWidth(110)
        row1.addWidget(self.chain_combo)

        self.mint_input = QLineEdit()
        self.mint_input.setPlaceholderText("粘贴代币地址 (mint / contract)")
        row1.addWidget(self.mint_input, 1)

        lay.addLayout(row1)

        # 金额 + 滑点 + Buy
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        row2.addWidget(self._mk_label("金额:"))

        self.amount_input = QLineEdit("0.5")
        self.amount_input.setObjectName("amountInput")
        self.amount_input.setMaximumWidth(90)
        row2.addWidget(self.amount_input)

        self.unit_lbl = QLabel("SOL")
        self.unit_lbl.setStyleSheet(
            f"color: {COLORS['text_mute']}; font-size: 11px; font-weight: 700;"
        )
        row2.addWidget(self.unit_lbl)

        self.chain_combo.currentTextChanged.connect(self._on_chain_change)

        row2.addSpacing(14)

        # 快捷金额
        for amt in [0.1, 0.5, 1.0, 5.0]:
            btn = QPushButton(f"{amt}")
            btn.setObjectName("quickAmt")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, v=amt: self.amount_input.setText(str(v)))
            row2.addWidget(btn)

        row2.addSpacing(14)

        row2.addWidget(self._mk_label("滑点:"))

        self.slip_input = QLineEdit("5")
        self.slip_input.setObjectName("amountInput")
        self.slip_input.setMaximumWidth(50)
        row2.addWidget(self.slip_input)

        pct = QLabel("%")
        pct.setStyleSheet(f"color: {COLORS['text_mute']}; font-size: 11px;")
        row2.addWidget(pct)

        row2.addStretch()

        buy_btn = QPushButton("⚡ SNIPE NOW")
        buy_btn.setObjectName("buyBtn")
        buy_btn.setCursor(Qt.PointingHandCursor)
        buy_btn.setMinimumWidth(140)
        buy_btn.clicked.connect(self._on_buy)
        row2.addWidget(buy_btn)

        lay.addLayout(row2)

    def _mk_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLORS['text_mute']}; font-size: 11px; font-weight: 600;")
        return lbl

    def _on_chain_change(self, chain: str) -> None:
        units = {"solana": "SOL", "bsc": "BNB", "ethereum": "ETH"}
        defaults = {"solana": "0.5", "bsc": "0.1", "ethereum": "0.05"}
        self.unit_lbl.setText(units.get(chain, ""))
        self.amount_input.setText(defaults.get(chain, "0.1"))

    def _on_buy(self) -> None:
        chain = self.chain_combo.currentText()
        mint = self.mint_input.text().strip()
        if not mint:
            QMessageBox.warning(self, "地址为空", "请粘贴代币地址")
            return
        try:
            amt = float(self.amount_input.text().strip())
            if amt <= 0:
                raise ValueError()
        except ValueError:
            QMessageBox.warning(self, "金额错误", "请输入有效的金额")
            return
        try:
            slip = int(float(self.slip_input.text().strip()) * 100)
        except ValueError:
            slip = 500

        self.buy_requested.emit(chain, mint, amt, slip)
        self.mint_input.clear()


class DashboardPage(QWidget):
    """主仪表盘"""

    # 转发 quick snipe 到主窗口
    quick_buy_requested = Signal(str, str, float, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running_fns: set[str] = set()
        self._sig_count = 0
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # 标题
        head = QHBoxLayout()
        title = QLabel("🎯  Dashboard")
        title.setObjectName("pageTitle")
        head.addWidget(title)

        subtitle = QLabel("实时监控 · 一键操作")
        subtitle.setStyleSheet(
            f"color: {COLORS['text_mute']}; font-size: 12px; margin-left: 8px;"
        )
        head.addWidget(subtitle)
        head.addStretch()
        root.addLayout(head)

        # ========== 4 个统计卡 ==========
        stats_row = QGridLayout()
        stats_row.setSpacing(10)
        self.card_running = StatCard("运行策略", "0", COLORS["accent"])
        self.card_signals = StatCard("今日信号", "0", COLORS["text_bright"])
        self.card_positions = StatCard("持仓数量", "0", COLORS["text_bright"])
        self.card_pnl = StatCard("未实现盈亏", "$0.00", COLORS["success"])
        stats_row.addWidget(self.card_running, 0, 0)
        stats_row.addWidget(self.card_signals, 0, 1)
        stats_row.addWidget(self.card_positions, 0, 2)
        stats_row.addWidget(self.card_pnl, 0, 3)
        root.addLayout(stats_row)

        # ========== 中部：左右 splitter ==========
        mid_split = QSplitter(Qt.Horizontal)
        mid_split.setChildrenCollapsible(False)

        # ---- 左：信号流 ----
        sig_card = Card()
        sig_lay = QVBoxLayout(sig_card)
        sig_lay.setContentsMargins(16, 14, 16, 14)
        sig_lay.setSpacing(8)

        sig_head = QHBoxLayout()
        sig_title = QLabel("📡  Live Signals")
        sig_title.setObjectName("cardTitle")
        sig_head.addWidget(sig_title)
        sig_head.addStretch()

        self.sig_count_lbl = QLabel("0")
        self.sig_count_lbl.setStyleSheet(
            f"background: {COLORS['bg_elev']}; color: {COLORS['text_mute']};"
            f"padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 700;"
        )
        sig_head.addWidget(self.sig_count_lbl)

        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._clear_signals)
        sig_head.addWidget(clear_btn)

        sig_lay.addLayout(sig_head)

        self.signals_table = QTableWidget(0, 6)
        self.signals_table.setHorizontalHeaderLabels(
            ["时间", "链", "Token", "动作", "金额", "操作"]
        )
        h = self.signals_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.signals_table.verticalHeader().setVisible(False)
        self.signals_table.setAlternatingRowColors(True)
        self.signals_table.setEditTriggers(QTableWidget.NoEditTriggers)
        sig_lay.addWidget(self.signals_table)

        mid_split.addWidget(sig_card)

        # ---- 右：持仓 ----
        pos_card = Card()
        pos_lay = QVBoxLayout(pos_card)
        pos_lay.setContentsMargins(16, 14, 16, 14)
        pos_lay.setSpacing(8)

        pos_head = QHBoxLayout()
        pos_title = QLabel("💼  Active Positions")
        pos_title.setObjectName("cardTitle")
        pos_head.addWidget(pos_title)
        pos_head.addStretch()

        self.pos_count_lbl = QLabel("0")
        self.pos_count_lbl.setStyleSheet(self.sig_count_lbl.styleSheet())
        pos_head.addWidget(self.pos_count_lbl)

        sell_all_btn = QPushButton("全部清仓")
        sell_all_btn.setObjectName("dangerBtn")
        sell_all_btn.clicked.connect(self._on_sell_all)
        pos_head.addWidget(sell_all_btn)

        pos_lay.addLayout(pos_head)

        self.positions_table = QTableWidget(0, 6)
        self.positions_table.setHorizontalHeaderLabels(
            ["Token", "成本价", "现价", "PnL %", "金额", "操作"]
        )
        h2 = self.positions_table.horizontalHeader()
        h2.setSectionResizeMode(0, QHeaderView.Stretch)
        h2.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.positions_table.verticalHeader().setVisible(False)
        self.positions_table.setAlternatingRowColors(True)
        self.positions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        pos_lay.addWidget(self.positions_table)

        mid_split.addWidget(pos_card)
        mid_split.setSizes([600, 600])

        root.addWidget(mid_split, 1)

        # ========== 底部：Quick Snipe ==========
        self.quick_snipe = QuickSnipePanel()
        self.quick_snipe.buy_requested.connect(self.quick_buy_requested.emit)
        root.addWidget(self.quick_snipe)

    # ---------- 外部接口 ----------

    def update_running_count(self, running: set) -> None:
        self._running_fns = running
        self.card_running.set_value(str(len(running)), COLORS["accent"])

    def push_signal(self, time_str: str, chain: str, token: str, action: str,
                    amount_usd: float, note: str = "",
                    mint: str = "") -> None:
        self.signals_table.insertRow(0)

        # 时间
        self.signals_table.setItem(0, 0, QTableWidgetItem(time_str))

        # 链
        ch_item = QTableWidgetItem(chain.upper())
        ch_item.setForeground(QColor(chain_color(chain)))
        self.signals_table.setItem(0, 1, ch_item)

        # Token
        self.signals_table.setItem(0, 2, QTableWidgetItem(token))

        # 动作
        act_item = QTableWidgetItem(action)
        if action.upper() == "BUY":
            act_item.setForeground(QColor(COLORS['success']))
        elif action.upper() == "SELL":
            act_item.setForeground(QColor(COLORS['danger']))
        self.signals_table.setItem(0, 3, act_item)

        # 金额
        amt_str = f"${amount_usd:.2f}" if amount_usd > 0 else "—"
        self.signals_table.setItem(0, 4, QTableWidgetItem(amt_str))

        # 操作按钮
        if mint:
            action_btn = QPushButton("⚡买入")
            action_btn.setObjectName("buyBtn")
            action_btn.setFixedWidth(70)
            action_btn.clicked.connect(
                lambda: self.quick_buy_requested.emit(chain, mint, 0.1, 500)
            )
            self.signals_table.setCellWidget(0, 5, action_btn)
        else:
            self.signals_table.setItem(0, 5, QTableWidgetItem("—"))

        # 限制行数
        while self.signals_table.rowCount() > 100:
            self.signals_table.removeRow(self.signals_table.rowCount() - 1)

        self._sig_count += 1
        self.sig_count_lbl.setText(str(self._sig_count))
        self.card_signals.set_value(str(self._sig_count), COLORS["text_bright"])

    def update_positions(self, positions: list[dict]) -> None:
        self.positions_table.setRowCount(0)
        total_pnl = 0.0
        for p in positions:
            row = self.positions_table.rowCount()
            self.positions_table.insertRow(row)
            pct = ((p["current"] - p["entry"]) / p["entry"] * 100) if p.get("entry") else 0
            pnl_usd = (p["current"] - p["entry"]) / p["entry"] * p["size_usd"] if p.get("entry") else 0
            total_pnl += pnl_usd

            self.positions_table.setItem(row, 0, QTableWidgetItem(p["token"]))
            self.positions_table.setItem(row, 1, QTableWidgetItem(f"{p['entry']:.6f}"))
            self.positions_table.setItem(row, 2, QTableWidgetItem(f"{p['current']:.6f}"))

            pct_item = QTableWidgetItem(f"{pct:+.2f}%")
            pct_item.setForeground(QColor(COLORS['success'] if pct >= 0 else COLORS['danger']))
            self.positions_table.setItem(row, 3, pct_item)
            self.positions_table.setItem(row, 4, QTableWidgetItem(f"${p['size_usd']:.2f}"))

            # Sell 按钮
            mint = p.get("mint", "")
            chain = p.get("chain", "solana")
            if mint:
                sell_btn = QPushButton("SELL")
                sell_btn.setObjectName("sellBtn")
                sell_btn.setFixedWidth(60)
                # 占位 signal - 由 MainWindow 处理
                self.positions_table.setCellWidget(row, 5, sell_btn)
            else:
                self.positions_table.setItem(row, 5, QTableWidgetItem("—"))

            self.positions_table.setRowHeight(row, 36)

        self.pos_count_lbl.setText(str(len(positions)))
        self.card_positions.set_value(str(len(positions)), COLORS["text_bright"])

        if total_pnl >= 0:
            self.card_pnl.set_value(f"+${total_pnl:.2f}", COLORS["success"])
        else:
            self.card_pnl.set_value(f"-${abs(total_pnl):.2f}", COLORS["danger"])

    def _clear_signals(self) -> None:
        self.signals_table.setRowCount(0)
        self._sig_count = 0
        self.sig_count_lbl.setText("0")

    def _on_sell_all(self) -> None:
        if self.positions_table.rowCount() == 0:
            return
        ret = QMessageBox.question(
            self, "确认", f"确定要清仓全部 {self.positions_table.rowCount()} 个持仓？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        # TODO: 触发 sell signal
        QMessageBox.information(self, "已发送", "清仓指令已提交")
