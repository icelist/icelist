"""
通用卡片 widget：StatCard（统计卡）、FunctionCard（功能卡）
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QGraphicsDropShadowEffect,
    QSizePolicy,
)

from ..theme import COLORS, chain_color


class Card(QFrame):
    """基础卡片，带阴影和圆角"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFrameShape(QFrame.StyledPanel)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)


class StatCard(Card):
    """统计卡：大数字 + 小标签"""

    def __init__(self, label: str, value: str = "0",
                 value_color: str | None = None, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(6)

        self.label = QLabel(label.upper())
        self.label.setObjectName("statLabel")
        self.value = QLabel(value)
        self.value.setObjectName("statValue")
        if value_color:
            self.value.setStyleSheet(f"color: {value_color};")

        lay.addWidget(self.label)
        lay.addWidget(self.value)
        lay.addStretch()

    def set_value(self, v: str, color: str | None = None) -> None:
        self.value.setText(v)
        if color:
            self.value.setStyleSheet(
                f"color: {color}; font-size: 22px; font-weight: 700;"
            )


class FunctionCard(Card):
    """功能卡：链徽章 + 功能名 + 说明 + 启停按钮"""

    toggled = Signal(str, bool)   # fn_code, is_running

    def __init__(self, fn_meta: dict, parent=None):
        super().__init__(parent)
        self.fn_meta = fn_meta
        self.fn_code = fn_meta["code"]
        self._running = False

        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        # 顶部行：链徽章 + 状态徽章
        top = QHBoxLayout()
        chain = fn_meta["chain"]
        badge = QLabel(f" {chain.upper()} ")
        badge.setStyleSheet(
            f"background: {chain_color(chain)}; color: #0d1117;"
            f"border-radius: 4px; padding: 2px 8px; font-weight: 700; font-size: 10px;"
        )
        badge.setFixedHeight(20)
        top.addWidget(badge)

        cat_badge = QLabel(f" {fn_meta['category']} ")
        cat_badge.setStyleSheet(
            f"background: {COLORS['bg_hover']}; color: {COLORS['text_mute']};"
            f"border-radius: 4px; padding: 2px 8px; font-size: 10px;"
        )
        top.addWidget(cat_badge)
        top.addStretch()

        self.status_badge = QLabel("STOPPED")
        self.status_badge.setObjectName("badgeStopped")
        top.addWidget(self.status_badge)
        lay.addLayout(top)

        # 标题
        title = QLabel(fn_meta["display"])
        title.setObjectName("cardTitle")
        lay.addWidget(title)

        # 代号
        code_lbl = QLabel(fn_meta["code"])
        code_lbl.setStyleSheet(f"color: {COLORS['text_mute']}; font-family: monospace; font-size: 11px;")
        lay.addWidget(code_lbl)

        # 描述
        desc = QLabel(fn_meta["desc"])
        desc.setObjectName("cardDesc")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addStretch()

        # 启停按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.toggle_btn = QPushButton("▶  启动")
        self.toggle_btn.setObjectName("primaryBtn")
        self.toggle_btn.setFixedHeight(32)
        self.toggle_btn.clicked.connect(self._on_toggle)
        btn_row.addWidget(self.toggle_btn)
        lay.addLayout(btn_row)

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
        # 重新应用 QSS（因为 objectName 变了）
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)
