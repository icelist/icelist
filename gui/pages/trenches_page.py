"""
Trenches 页面 —— 实时代币发现流
参考 BullX Trenches / Photon Pulse / Axiom Memescope

布局：3 列
  [🆕 刚创建]   [🚀 即将毕业]   [🎓 已毕业]
  自动滚动刷新，每个卡片都有内嵌买入控件
"""
from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer, QObject
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
    QPushButton, QComboBox, QCheckBox, QMessageBox,
)

from ..theme import COLORS, chain_color
from ..widgets.token_card import TokenCard
from core.launchpads import fetch_all_upcoming
from core.logger import logger


class _Fetcher(QObject):
    done = Signal(list)
    error = Signal(str)


class TokenColumn(QFrame):
    """单列：标题 + 可滚动的 TokenCard 列表"""

    buy_requested = Signal(str, str, float, int)    # chain, mint, amt, slippage
    sell_requested = Signal(str, str, int, int)     # chain, mint, pct, slippage

    def __init__(self, title: str, emoji: str, color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("widgetCard")
        self._cards: dict[str, TokenCard] = {}  # mint -> card

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # 标题栏
        head = QHBoxLayout()
        title_lbl = QLabel(f"{emoji}  {title}")
        title_lbl.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: 800; letter-spacing: 0.5px;"
        )
        head.addWidget(title_lbl)
        head.addStretch()

        self.count_lbl = QLabel("0")
        self.count_lbl.setStyleSheet(
            f"background: {COLORS['bg_elev']}; color: {COLORS['text_mute']};"
            f"padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 700;"
        )
        head.addWidget(self.count_lbl)
        lay.addLayout(head)

        # 可滚动区
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.content = QWidget()
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(0, 0, 6, 0)
        self.content_lay.setSpacing(10)
        self.content_lay.addStretch()

        self.scroll.setWidget(self.content)
        lay.addWidget(self.scroll, 1)

    def upsert_card(self, event: dict) -> None:
        """插入或更新卡片"""
        mint = event.get("token") or ""
        if not mint:
            return

        if mint in self._cards:
            # 更新现有卡片的指标
            c = self._cards[mint]
            extra = event.get("extra") or {}
            c.update_metrics(
                mcap=extra.get("mc_usd"),
                vol=extra.get("volume_24h"),
            )
            return

        # 新卡片
        extra = event.get("extra") or {}
        now_ts = datetime.now().timestamp()
        start_ts = event.get("start_ts") or 0
        try:
            if start_ts:
                t = float(start_ts)
                if t > 1e12: t /= 1000
                age = max(0, int(now_ts - t))
            else:
                age = 0
        except (TypeError, ValueError):
            age = 0

        progress = extra.get("progress", -1)
        mcap = extra.get("mc_usd") or 0

        card = TokenCard(
            chain=event.get("chain", "solana"),
            mint=mint,
            symbol=event.get("name", "?")[:16],
            name=event.get("source", ""),
            mcap_usd=mcap,
            volume_24h=extra.get("volume_24h") or 0,
            age_sec=age,
            safety="unknown",
            is_new=(age < 300),  # 5分钟内算新
            is_hot=(mcap > 50000 and age < 3600),  # 1h 内 5w+ mc
            progress=progress if progress >= 0 else -1,
        )
        card.buy_requested.connect(
            lambda m, a, s, ch=event.get("chain", "solana"):
                self.buy_requested.emit(ch, m, a, s)
        )
        card.sell_requested.connect(
            lambda m, p, s, ch=event.get("chain", "solana"):
                self.sell_requested.emit(ch, m, p, s)
        )

        self._cards[mint] = card
        # 插入到顶部
        self.content_lay.insertWidget(0, card)

        # 限制数量（每列最多 30 张）
        if len(self._cards) > 30:
            self._prune()

        self.count_lbl.setText(str(len(self._cards)))

    def _prune(self) -> None:
        # 移除最下面的卡片
        while len(self._cards) > 30:
            # 找最底部 widget
            for i in range(self.content_lay.count() - 1, -1, -1):
                item = self.content_lay.itemAt(i)
                w = item.widget() if item else None
                if isinstance(w, TokenCard):
                    self._cards.pop(w.mint, None)
                    w.deleteLater()
                    self.content_lay.removeWidget(w)
                    break
            else:
                break

    def clear_all(self) -> None:
        for m in list(self._cards.keys()):
            c = self._cards.pop(m)
            c.deleteLater()
            self.content_lay.removeWidget(c)
        self.count_lbl.setText("0")


class TrenchesPage(QWidget):
    """主 Trenches 页面：3 列布局"""

    buy_requested = Signal(str, str, float, int)
    sell_requested = Signal(str, str, int, int)

    def __init__(self, runner, parent=None):
        super().__init__(parent)
        self.runner = runner

        self.fetcher = _Fetcher()
        self.fetcher.done.connect(self._on_data)
        self.fetcher.error.connect(self._on_error)

        self._build_ui()

        # 自动刷新（每 30 秒）
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self.refresh)
        self.auto_timer.start(30_000)

        QTimer.singleShot(500, self.refresh)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # 标题栏
        head = QHBoxLayout()
        title = QLabel("🎯  Trenches")
        title.setObjectName("pageTitle")
        head.addWidget(title)

        subtitle = QLabel("实时代币发现 · 一键买入")
        subtitle.setStyleSheet(
            f"color: {COLORS['text_mute']}; font-size: 12px; margin-left: 8px;"
        )
        head.addWidget(subtitle)

        head.addStretch()

        # 过滤：链选择
        head.addWidget(self._mk_label("链:"))
        self.chain_filter = QComboBox()
        self.chain_filter.addItems(["全部", "solana", "bsc", "ethereum"])
        self.chain_filter.setFixedWidth(110)
        self.chain_filter.currentTextChanged.connect(self._rerender)
        head.addWidget(self.chain_filter)

        # 刷新按钮
        self.status_lbl = QLabel("准备中...")
        self.status_lbl.setStyleSheet(f"color: {COLORS['text_mute']}; font-size: 11px;")
        head.addWidget(self.status_lbl)

        self.auto_chk = QCheckBox("自动刷新")
        self.auto_chk.setChecked(True)
        self.auto_chk.toggled.connect(self._on_auto_toggle)
        head.addWidget(self.auto_chk)

        refresh_btn = QPushButton("🔄  刷新")
        refresh_btn.clicked.connect(self.refresh)
        head.addWidget(refresh_btn)

        root.addLayout(head)

        # ========== 3 列 ==========
        cols_row = QHBoxLayout()
        cols_row.setSpacing(12)

        self.col_new = TokenColumn("刚上线", "🆕", COLORS['accent'])
        self.col_bonding = TokenColumn("冲刺中", "🚀", COLORS['warn'])
        self.col_graduated = TokenColumn("已毕业", "🎓", COLORS['success'])

        for col in [self.col_new, self.col_bonding, self.col_graduated]:
            col.buy_requested.connect(self.buy_requested.emit)
            col.sell_requested.connect(self.sell_requested.emit)
            cols_row.addWidget(col, 1)

        root.addLayout(cols_row, 1)

        # 底部提示
        hint = QLabel(
            f"💡 每个代币卡片有完整交易控件：快捷金额(0.1/0.5/1/5)、自定义金额输入、滑点、BUY/SELL。"
            f"数据每 30 秒从 Pump.fun / Jupiter Studio / DEXScreener 聚合。"
        )
        hint.setStyleSheet(f"color: {COLORS['text_mute']}; font-size: 11px;")
        hint.setWordWrap(True)
        root.addWidget(hint)

    def _mk_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLORS['text_mute']}; font-size: 11px; font-weight: 600;")
        return lbl

    def _on_auto_toggle(self, checked: bool) -> None:
        if checked:
            self.auto_timer.start(30_000)
        else:
            self.auto_timer.stop()

    # ---------- 刷新 ----------

    def refresh(self) -> None:
        self.status_lbl.setText("🔄 抓取中...")

        async def run():
            try:
                data = await fetch_all_upcoming()
                self.fetcher.done.emit(data)
            except Exception as e:
                self.fetcher.error.emit(str(e))

        loop = self.runner._loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(run(), loop)
        else:
            self.status_lbl.setText("❌ 事件循环未就绪")

    def _on_data(self, events: list) -> None:
        # 按 chain 过滤
        chain_f = self.chain_filter.currentText()
        if chain_f != "全部":
            events = [e for e in events if e.get("chain") == chain_f]

        self._all_events = events
        self._rerender()

        ts = datetime.now().strftime("%H:%M:%S")
        self.status_lbl.setText(f"✓ {len(events)} 条 · {ts}")

    def _rerender(self) -> None:
        if not hasattr(self, '_all_events'):
            return

        events = self._all_events
        chain_f = self.chain_filter.currentText()
        if chain_f != "全部":
            events = [e for e in events if e.get("chain") == chain_f]

        # 分类
        new_events, bonding_events, grad_events = [], [], []
        now = datetime.now().timestamp()

        for e in events:
            status = str(e.get("status", "")).lower()
            extra = e.get("extra") or {}
            progress = extra.get("progress", -1)

            if "graduated" in status:
                grad_events.append(e)
            elif "bonding" in status or (0 < progress < 100):
                bonding_events.append(e)
            else:
                # 按年龄判断：30 分钟内=新，否则归 bonding
                start_ts = e.get("start_ts") or 0
                try:
                    if start_ts:
                        t = float(start_ts)
                        if t > 1e12: t /= 1000
                        age = now - t
                    else:
                        age = 0
                except (TypeError, ValueError):
                    age = 0

                if age > 0 and age < 1800:  # 30 分钟内
                    new_events.append(e)
                else:
                    bonding_events.append(e)

        # 清空 + 重填
        self.col_new.clear_all()
        self.col_bonding.clear_all()
        self.col_graduated.clear_all()

        for e in new_events[:20]:
            self.col_new.upsert_card(e)
        for e in bonding_events[:20]:
            self.col_bonding.upsert_card(e)
        for e in grad_events[:20]:
            self.col_graduated.upsert_card(e)

    def _on_error(self, err: str) -> None:
        self.status_lbl.setText(f"❌ {err[:40]}")
