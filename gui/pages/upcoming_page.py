"""
即将打新 —— 实时聚合 Jupiter Studio / Pump.fun / Binance Launchpool / HODLer / CoinList / DEXScreener
"""
from __future__ import annotations
import asyncio
import webbrowser
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QMessageBox,
)

from ..theme import COLORS, chain_color
from core.launchpads import fetch_all_upcoming, format_ts
from core.logger import logger


class _Fetcher(QObject):
    """在 runner 的 asyncio loop 中跑抓取，结果通过 Signal 回到 UI"""
    done = Signal(list)
    error = Signal(str)


class UpcomingPage(QWidget):
    """即将打新活动看板"""

    def __init__(self, runner, parent=None):
        super().__init__(parent)
        self.runner = runner   # StrategyRunner（用它的 asyncio loop 拉数据）
        self._all_events: list[dict] = []
        self.fetcher = _Fetcher()
        self.fetcher.done.connect(self._on_data)
        self.fetcher.error.connect(self._on_error)
        self._build_ui()

        # 自动刷新计时器（每 60 秒）
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self.refresh)
        self.auto_timer.start(60_000)

        # 进入页面先抓一次
        QTimer.singleShot(500, self.refresh)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(12)

        title = QLabel("即将打新 / 新开池活动")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "实时聚合 Jupiter Studio / Pump.fun / Binance Launchpool / Binance HODLer / CoinList / DEXScreener"
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        # 工具栏
        tools = QHBoxLayout()
        tools.addWidget(QLabel("链："))
        self.chain_filter = QComboBox()
        self.chain_filter.addItems(["ALL", "solana", "bsc", "ethereum", "base"])
        self.chain_filter.currentTextChanged.connect(self._render)
        tools.addWidget(self.chain_filter)

        tools.addWidget(QLabel("状态："))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["ALL", "upcoming", "live", "trending", "bonding", "graduated"])
        self.status_filter.currentTextChanged.connect(self._render)
        tools.addWidget(self.status_filter)

        tools.addStretch()

        self.status_lbl = QLabel("准备中...")
        self.status_lbl.setStyleSheet(f"color: {COLORS['text_mute']};")
        tools.addWidget(self.status_lbl)

        self.refresh_btn = QPushButton("🔄  立即刷新")
        self.refresh_btn.clicked.connect(self.refresh)
        tools.addWidget(self.refresh_btn)

        root.addLayout(tools)

        # 表格
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["链", "来源", "项目", "状态", "时间", "操作"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table, 1)

        # 底部提示
        hint = QLabel(
            "💡 数据来自各平台公开 API，每 60 秒自动刷新。点击操作列「访问」直接打开官方页面。"
        )
        hint.setStyleSheet(f"color: {COLORS['text_mute']}; font-size: 11px;")
        root.addWidget(hint)

    # ---------- 刷新 ----------

    def refresh(self) -> None:
        self.status_lbl.setText("🔄 正在抓取...")
        self.refresh_btn.setEnabled(False)

        async def run():
            try:
                data = await fetch_all_upcoming()
                self.fetcher.done.emit(data)
            except Exception as e:
                self.fetcher.error.emit(str(e))

        # 在 runner 的 asyncio loop 里跑
        loop = self.runner._loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(run(), loop)
        else:
            self.status_lbl.setText("❌ 事件循环未就绪")
            self.refresh_btn.setEnabled(True)

    def _on_data(self, events: list[dict]) -> None:
        self._all_events = events
        self._render()
        ts = datetime.now().strftime("%H:%M:%S")
        self.status_lbl.setText(f"✓ 已加载 {len(events)} 条 @ {ts}")
        self.refresh_btn.setEnabled(True)
        logger.info(f"[upcoming] loaded {len(events)} events")

    def _on_error(self, err: str) -> None:
        self.status_lbl.setText(f"❌ 抓取失败：{err[:50]}")
        self.refresh_btn.setEnabled(True)

    def _render(self) -> None:
        chain = self.chain_filter.currentText()
        status = self.status_filter.currentText()

        filtered = []
        for e in self._all_events:
            if chain != "ALL" and e.get("chain") != chain:
                continue
            if status != "ALL":
                s = (e.get("status") or "").lower()
                if status not in s:
                    continue
            filtered.append(e)

        self.table.setRowCount(0)
        for e in filtered:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # 链 badge
            ch = e.get("chain", "?")
            ch_item = QTableWidgetItem(ch.upper())
            ch_item.setForeground(QColor(chain_color(ch)))
            self.table.setItem(row, 0, ch_item)

            self.table.setItem(row, 1, QTableWidgetItem(e.get("source", "")))

            name = e.get("name") or "?"
            token = e.get("token", "")
            if token:
                name = f"{name}\n{token[:8]}...{token[-4:]}" if len(token) > 16 else f"{name}\n{token}"
            name_item = QTableWidgetItem(name)
            self.table.setItem(row, 2, name_item)

            status_text = e.get("status", "?")
            status_item = QTableWidgetItem(status_text)
            s_lower = str(status_text).lower()
            if "live" in s_lower or "trend" in s_lower:
                status_item.setForeground(QColor(COLORS["success"]))
            elif "upcoming" in s_lower:
                status_item.setForeground(QColor(COLORS["warn"]))
            elif "graduated" in s_lower:
                status_item.setForeground(QColor(COLORS["accent2"]))
            self.table.setItem(row, 3, status_item)

            self.table.setItem(row, 4, QTableWidgetItem(format_ts(e.get("start_ts"))))

            # 操作按钮
            btn = QPushButton("访问")
            btn.setObjectName("primaryBtn")
            url = e.get("website") or ""
            if url:
                btn.clicked.connect(lambda _, u=url: webbrowser.open(u))
            else:
                btn.setEnabled(False)
            self.table.setCellWidget(row, 5, btn)

            self.table.setRowHeight(row, 50)
