"""
Dashboard 页面 —— 总览：4 个统计卡片 + 最新信号表 + 持仓表
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QGridLayout,
)

from ..theme import COLORS
from ..widgets.cards import StatCard, Card


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._running_fns: set[str] = set()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(18)

        # 标题
        title = QLabel("仪表盘")
        title.setObjectName("pageTitle")
        subtitle = QLabel("实时监控运行中的策略、信号和持仓")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        # 4 个统计卡片
        stats_row = QGridLayout()
        stats_row.setSpacing(12)
        self.card_running = StatCard("运行中策略", "0", COLORS["accent"])
        self.card_signals = StatCard("今日信号", "0", COLORS["text_bright"])
        self.card_positions = StatCard("持仓数", "0", COLORS["text_bright"])
        self.card_pnl = StatCard("未实现盈亏", "$0.00", COLORS["success"])
        stats_row.addWidget(self.card_running, 0, 0)
        stats_row.addWidget(self.card_signals, 0, 1)
        stats_row.addWidget(self.card_positions, 0, 2)
        stats_row.addWidget(self.card_pnl, 0, 3)
        root.addLayout(stats_row)

        # 双表格
        tables_row = QHBoxLayout()
        tables_row.setSpacing(12)

        # 最新信号
        sig_card = Card()
        sig_lay = QVBoxLayout(sig_card)
        sig_lay.setContentsMargins(16, 14, 16, 14)
        sig_title = QLabel("📡  最新信号")
        sig_title.setObjectName("cardTitle")
        sig_lay.addWidget(sig_title)
        self.signals_table = QTableWidget(0, 5)
        self.signals_table.setHorizontalHeaderLabels(
            ["时间", "Token", "动作", "金额", "备注"]
        )
        self.signals_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.signals_table.verticalHeader().setVisible(False)
        self.signals_table.setAlternatingRowColors(True)
        self.signals_table.setEditTriggers(QTableWidget.NoEditTriggers)
        sig_lay.addWidget(self.signals_table)
        tables_row.addWidget(sig_card, 1)

        # 持仓
        pos_card = Card()
        pos_lay = QVBoxLayout(pos_card)
        pos_lay.setContentsMargins(16, 14, 16, 14)
        pos_title = QLabel("💼  活跃持仓")
        pos_title.setObjectName("cardTitle")
        pos_lay.addWidget(pos_title)
        self.positions_table = QTableWidget(0, 5)
        self.positions_table.setHorizontalHeaderLabels(
            ["Token", "成本价", "现价", "盈亏 %", "金额"]
        )
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.positions_table.verticalHeader().setVisible(False)
        self.positions_table.setAlternatingRowColors(True)
        self.positions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        pos_lay.addWidget(self.positions_table)
        tables_row.addWidget(pos_card, 1)

        root.addLayout(tables_row, 1)

    # ---------- 外部更新接口 ----------

    def update_running_count(self, running: set[str]) -> None:
        self._running_fns = running
        self.card_running.set_value(str(len(running)), COLORS["accent"])

    def push_signal(self, time_str: str, token: str, action: str,
                    amount_usd: float, note: str = "") -> None:
        row = 0
        self.signals_table.insertRow(row)
        items = [
            QTableWidgetItem(time_str),
            QTableWidgetItem(token),
            QTableWidgetItem(action),
            QTableWidgetItem(f"${amount_usd:.2f}"),
            QTableWidgetItem(note),
        ]
        # 动作着色
        if action.upper() == "BUY":
            items[2].setForeground(Qt.green)
        else:
            items[2].setForeground(Qt.red)
        for col, it in enumerate(items):
            self.signals_table.setItem(row, col, it)
        # 限制行数
        while self.signals_table.rowCount() > 50:
            self.signals_table.removeRow(self.signals_table.rowCount() - 1)
        # 更新卡片
        self.card_signals.set_value(str(self.signals_table.rowCount()),
                                    COLORS["text_bright"])

    def update_positions(self, positions: list[dict]) -> None:
        """positions: [{token, entry, current, size_usd}, ...]"""
        self.positions_table.setRowCount(0)
        total_pnl = 0.0
        for p in positions:
            row = self.positions_table.rowCount()
            self.positions_table.insertRow(row)
            pct = ((p["current"] - p["entry"]) / p["entry"] * 100) if p.get("entry") else 0
            pnl_usd = (p["current"] - p["entry"]) / p["entry"] * p["size_usd"] if p.get("entry") else 0
            total_pnl += pnl_usd
            pct_item = QTableWidgetItem(f"{pct:+.2f}%")
            pct_item.setForeground(Qt.green if pct >= 0 else Qt.red)
            self.positions_table.setItem(row, 0, QTableWidgetItem(p["token"]))
            self.positions_table.setItem(row, 1, QTableWidgetItem(f"{p['entry']:.6f}"))
            self.positions_table.setItem(row, 2, QTableWidgetItem(f"{p['current']:.6f}"))
            self.positions_table.setItem(row, 3, pct_item)
            self.positions_table.setItem(row, 4, QTableWidgetItem(f"${p['size_usd']:.2f}"))

        self.card_positions.set_value(str(len(positions)), COLORS["text_bright"])
        if total_pnl >= 0:
            self.card_pnl.set_value(f"+${total_pnl:.2f}", COLORS["success"])
        else:
            self.card_pnl.set_value(f"-${abs(total_pnl):.2f}", COLORS["error"])
