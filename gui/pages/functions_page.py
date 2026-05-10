"""
Functions 页面 —— 16 个功能卡片网格，按链分 Tab
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QGridLayout, QTabWidget,
)

from ..widgets.cards import FunctionCard
from ..theme import COLORS, chain_color

from functions import REGISTRY, functions_for_chain


class FunctionsPage(QWidget):
    """显示所有功能卡片，按链分 Tab；启停通过 toggle 信号上抛"""

    fn_toggled = Signal(str, bool)  # fn_code, is_running

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, FunctionCard] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(12)

        title = QLabel("功能列表")
        title.setObjectName("pageTitle")
        subtitle = QLabel("选择需要启动的链上狙击 / 打新 / 跟单功能（运行前请先在设置中配置 RPC 与钱包）")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        for chain, label, icon in [
            ("solana", "◎  Solana", "sol"),
            ("bsc",    "⬢  BNB Chain", "bsc"),
            ("ethereum", "◆  Ethereum", "eth"),
        ]:
            tabs.addTab(self._build_chain_grid(chain), label)

        root.addWidget(tabs, 1)

    def _build_chain_grid(self, chain: str) -> QWidget:
        container = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(14)
        grid.setContentsMargins(4, 14, 4, 14)

        fns = functions_for_chain(chain)
        for i, fn in enumerate(fns):
            card = FunctionCard(fn)
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
