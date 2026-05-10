"""
Functions Page —— 策略控制台
每个策略卡带参数设置 + 运行状态 + 启停按钮
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QScrollArea, QTabWidget, QFrame, QPushButton, QLineEdit,
    QSizePolicy,
)

from ..theme import COLORS, chain_color
from functions import REGISTRY, functions_for_chain


FN_ICONS = {
    "sniper": "🎯",
    "copytrade": "👥",
    "launchpad": "🚀",
    "meme": "🔥",
}


class StrategyCard(QFrame):
    """策略卡 —— 标题 + 参数 + 启停"""

    toggled = Signal(str, bool)

    def __init__(self, fn_meta: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("widgetCard")
        self.fn_code = fn_meta["code"]
        self.fn_meta = fn_meta
        self._running = False
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        # 顶部：链徽章 + 类型徽章 + 状态
        top = QHBoxLayout()
        chain = fn_meta["chain"]
        chain_b = QLabel(chain.upper())
        chain_b.setStyleSheet(
            f"background: {chain_color(chain)}; color: #0a0e14;"
            f"border-radius: 4px; padding: 2px 7px; font-weight: 800; font-size: 10px;"
            f"letter-spacing: 1px;"
        )
        chain_b.setFixedHeight(18)
        top.addWidget(chain_b)

        icon = FN_ICONS.get(fn_meta["category"], "•")
        cat_b = QLabel(f"{icon} {fn_meta['category']}")
        cat_b.setStyleSheet(
            f"color: {COLORS['text_mute']}; background: {COLORS['bg_elev']};"
            f"border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: 600;"
        )
        top.addWidget(cat_b)
        top.addStretch()

        self.status_badge = QLabel("STOPPED")
        self.status_badge.setObjectName("badgeStopped")
        top.addWidget(self.status_badge)
        lay.addLayout(top)

        # 标题
        title = QLabel(fn_meta["display"])
        title.setObjectName("cardTitle")
        lay.addWidget(title)

        # 代号 + 描述
        code_lbl = QLabel(fn_meta["code"])
        code_lbl.setStyleSheet(
            f"color: {COLORS['text_mute']}; font-family: 'Cascadia Mono', monospace; font-size: 11px;"
        )
        lay.addWidget(code_lbl)

        desc = QLabel(fn_meta["desc"])
        desc.setObjectName("cardDesc")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addStretch()

        # 参数行：买入金额 + 止盈%
        params = QHBoxLayout()
        params.setSpacing(6)

        params.addWidget(self._mk_label("买入:"))
        self.amount_input = QLineEdit(self._default_amount())
        self.amount_input.setObjectName("amountInput")
        self.amount_input.setMaximumWidth(70)
        params.addWidget(self.amount_input)

        unit_lbl = QLabel(self._unit())
        unit_lbl.setStyleSheet(f"color: {COLORS['text_mute']}; font-size: 11px; font-weight: 600;")
        params.addWidget(unit_lbl)

        params.addSpacing(10)

        params.addWidget(self._mk_label("止盈:"))
        self.tp_input = QLineEdit("200")
        self.tp_input.setObjectName("amountInput")
        self.tp_input.setMaximumWidth(50)
        params.addWidget(self.tp_input)
        params.addWidget(self._mk_unit("%"))

        params.addSpacing(8)

        params.addWidget(self._mk_label("止损:"))
        self.sl_input = QLineEdit("50")
        self.sl_input.setObjectName("amountInput")
        self.sl_input.setMaximumWidth(50)
        params.addWidget(self.sl_input)
        params.addWidget(self._mk_unit("%"))

        params.addStretch()

        self.toggle_btn = QPushButton("▶  启动")
        self.toggle_btn.setObjectName("primaryBtn")
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setMinimumWidth(90)
        self.toggle_btn.clicked.connect(self._on_toggle)
        params.addWidget(self.toggle_btn)

        lay.addLayout(params)

    def _mk_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {COLORS['text_mute']}; font-size: 11px; font-weight: 600;"
        )
        return lbl

    def _mk_unit(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLORS['text_mute']}; font-size: 11px;")
        return lbl

    def _default_amount(self) -> str:
        return {"solana": "0.5", "bsc": "0.1", "ethereum": "0.05"}.get(
            self.fn_meta["chain"], "0.1"
        )

    def _unit(self) -> str:
        return {"solana": "SOL", "bsc": "BNB", "ethereum": "ETH"}.get(
            self.fn_meta["chain"], "?"
        )

    def _on_toggle(self) -> None:
        self._running = not self._running
        self._refresh_ui()
        self.toggled.emit(self.fn_code, self._running)

    def set_running(self, running: bool) -> None:
        if self._running == running:
            return
        self._running = running
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        if self._running:
            self.toggle_btn.setText("■  停止")
            self.toggle_btn.setObjectName("dangerBtn")
            self.status_badge.setText("RUNNING")
            self.status_badge.setObjectName("badgeRunning")
        else:
            self.toggle_btn.setText("▶  启动")
            self.toggle_btn.setObjectName("primaryBtn")
            self.status_badge.setText("STOPPED")
            self.status_badge.setObjectName("badgeStopped")
        for w in [self.toggle_btn, self.status_badge]:
            w.style().unpolish(w)
            w.style().polish(w)

    def get_params(self) -> dict:
        try:
            amt = float(self.amount_input.text())
        except ValueError:
            amt = 0.1
        try:
            tp = float(self.tp_input.text())
        except ValueError:
            tp = 200
        try:
            sl = float(self.sl_input.text())
        except ValueError:
            sl = 50
        return {"amount": amt, "tp_pct": tp, "sl_pct": sl}


class FunctionsPage(QWidget):
    fn_toggled = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, StrategyCard] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # 标题
        head = QHBoxLayout()
        title = QLabel("⚡  策略控制台")
        title.setObjectName("pageTitle")
        head.addWidget(title)

        subtitle = QLabel("启停 16 个细分策略 · 每个策略独立参数")
        subtitle.setStyleSheet(
            f"color: {COLORS['text_mute']}; font-size: 12px; margin-left: 8px;"
        )
        head.addWidget(subtitle)
        head.addStretch()
        root.addLayout(head)

        # Tab 切换链
        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        for chain, label in [
            ("solana", "◎  Solana"),
            ("bsc", "⬢  BNB"),
            ("ethereum", "◆  Ethereum"),
        ]:
            tabs.addTab(self._build_chain_grid(chain), label)

        root.addWidget(tabs, 1)

    def _build_chain_grid(self, chain: str) -> QWidget:
        container = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(12)
        grid.setContentsMargins(4, 14, 4, 14)

        fns = functions_for_chain(chain)
        for i, fn in enumerate(fns):
            card = StrategyCard(fn)
            card.toggled.connect(self.fn_toggled.emit)
            self._cards[fn["code"]] = card
            grid.addWidget(card, i // 2, i % 2)

        grid.setRowStretch(len(fns), 1)
        scroll.setWidget(inner)

        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll)
        return container

    def set_running(self, fn_code: str, running: bool) -> None:
        if fn_code in self._cards:
            self._cards[fn_code].set_running(running)

    def get_params(self, fn_code: str) -> dict:
        if fn_code in self._cards:
            return self._cards[fn_code].get_params()
        return {}
