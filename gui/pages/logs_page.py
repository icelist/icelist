"""
Logs 页面 —— 实时日志流，支持级别过滤、清空、导出
"""
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QTextCharFormat, QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit,
    QComboBox, QFileDialog, QCheckBox,
)

from ..theme import COLORS


LEVEL_COLORS = {
    "DEBUG":   COLORS["text_mute"],
    "INFO":    COLORS["accent"],
    "SUCCESS": COLORS["success"],
    "WARNING": COLORS["warn"],
    "ERROR":   COLORS["danger"],
    "CRITICAL": "#ff3860",
}


class LogsPage(QWidget):
    MAX_LINES = 5000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(12)

        title = QLabel("实时日志")
        title.setObjectName("pageTitle")
        sub = QLabel("所有策略、交易、错误的实时流。可按级别过滤、导出到文件。")
        sub.setObjectName("pageSubtitle")
        root.addWidget(title)
        root.addWidget(sub)

        # 工具栏
        tools = QHBoxLayout()
        tools.addWidget(QLabel("级别："))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["ALL", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR"])
        tools.addWidget(self.level_combo)

        self.autoscroll = QCheckBox("自动滚动")
        self.autoscroll.setChecked(True)
        tools.addWidget(self.autoscroll)

        tools.addStretch()

        clear_btn = QPushButton("🗑  清空")
        clear_btn.clicked.connect(self._on_clear)
        tools.addWidget(clear_btn)

        export_btn = QPushButton("💾  导出")
        export_btn.clicked.connect(self._on_export)
        tools.addWidget(export_btn)
        root.addLayout(tools)

        # 日志文本框
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(self.MAX_LINES)
        font = QFont("Consolas, Menlo, Monaco, monospace", 11)
        font.setStyleHint(QFont.Monospace)
        self.view.setFont(font)
        self.view.setStyleSheet(
            f"QPlainTextEdit {{ background: #0a0e14; color: {COLORS['text']};"
            f"border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 10px; }}"
        )
        root.addWidget(self.view, 1)

    @Slot(str, str)
    def append_log(self, level: str, msg: str) -> None:
        """接收外部信号的日志"""
        sel = self.level_combo.currentText()
        if sel != "ALL" and level != sel:
            return

        ts = datetime.now().strftime("%H:%M:%S")
        color = LEVEL_COLORS.get(level, COLORS["text"])
        # 用 HTML 高亮级别
        html = (
            f'<span style="color:{COLORS["text_mute"]}">{ts}</span> '
            f'<span style="color:{color}; font-weight:700">[{level:<7}]</span> '
            f'<span style="color:{COLORS["text"]}">{msg}</span>'
        )
        self.view.appendHtml(html)
        if self.autoscroll.isChecked():
            sb = self.view.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _on_clear(self) -> None:
        self.view.clear()

    def _on_export(self) -> None:
        default = f"chain-sniper-{datetime.now():%Y%m%d_%H%M%S}.log"
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", default, "Log (*.log)")
        if not path:
            return
        Path(path).write_text(self.view.toPlainText(), encoding="utf-8")
