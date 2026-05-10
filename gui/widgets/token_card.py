"""
Token Card —— sniper terminal 核心 widget

参考 BullX/Photon/Axiom：每个代币一张卡，带：
  - 代币符号 + 地址（可复制）
  - 实时价格 + mcap + volume + holders
  - 安全徽章（✓ safe / ⚠ warn / ✗ danger）
  - 快捷金额按钮（0.1 / 0.5 / 1 / 5 SOL）
  - 自定义金额输入框
  - 滑点设置
  - Buy / Sell 大按钮
  - 详情按钮（打开浏览器看 chart）
"""
from __future__ import annotations
import webbrowser
from decimal import Decimal
from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QClipboard, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLineEdit, QSizePolicy, QButtonGroup, QToolTip,
    QApplication,
)

from ..theme import COLORS, chain_color


class QuickAmountButton(QPushButton):
    """点击填充金额到输入框"""
    def __init__(self, amount: float, unit: str = "SOL"):
        super().__init__(f"{amount} {unit}")
        self.amount = amount
        self.setObjectName("quickAmt")
        self.setCursor(Qt.PointingHandCursor)


class TokenCard(QFrame):
    """
    专业 sniper 代币卡片
    
    信号：
      buy_requested(mint, amount_sol, slippage_bps)   用户点 BUY
      sell_requested(mint, percent, slippage_bps)     用户点 SELL
      detail_requested(mint)                          用户点详情
    """

    buy_requested = Signal(str, float, int)      # mint, sol_amount, slippage_bps
    sell_requested = Signal(str, int, int)       # mint, percent, slippage_bps
    detail_requested = Signal(str)

    # 默认预设金额（可在设置中修改）
    PRESET_AMOUNTS_SOL = [0.1, 0.5, 1.0, 5.0]
    PRESET_AMOUNTS_ETH = [0.01, 0.05, 0.1, 0.5]
    PRESET_AMOUNTS_BNB = [0.05, 0.1, 0.5, 1.0]

    def __init__(self,
                 chain: str,
                 mint: str,
                 symbol: str = "?",
                 name: str = "",
                 price_usd: float = 0.0,
                 mcap_usd: float = 0.0,
                 volume_24h: float = 0.0,
                 holders: int = 0,
                 dev_percent: float = 0.0,
                 liquidity_usd: float = 0.0,
                 age_sec: int = 0,
                 safety: str = "unknown",      # safe/warn/danger/unknown
                 is_new: bool = False,
                 is_hot: bool = False,
                 progress: float = -1,         # bonding curve 进度，-1 表示不显示
                 parent=None):
        super().__init__(parent)
        self.setObjectName("tokenCard")
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.chain = chain
        self.mint = mint
        self.symbol = symbol
        self.name = name
        self._safety = safety

        self._build_ui(price_usd, mcap_usd, volume_24h, holders,
                       dev_percent, liquidity_usd, age_sec, progress,
                       is_new, is_hot)

    # ---------- UI 构建 ----------

    def _build_ui(self, price_usd, mcap_usd, volume_24h, holders,
                  dev_percent, liquidity_usd, age_sec, progress,
                  is_new, is_hot):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        # ========== Row 1: 符号 + 链徽章 + 状态徽章 ==========
        head = QHBoxLayout()
        head.setSpacing(8)

        # 链徽章
        chain_badge = QLabel(self.chain.upper())
        chain_badge.setStyleSheet(
            f"background: {chain_color(self.chain)}; color: #0a0e14;"
            f"border-radius: 4px; padding: 2px 7px; font-weight: 800; font-size: 10px;"
            f"letter-spacing: 1px;"
        )
        chain_badge.setFixedHeight(18)
        head.addWidget(chain_badge)

        # 符号
        sym_lbl = QLabel(self.symbol[:20])
        sym_lbl.setObjectName("tokenSymbol")
        head.addWidget(sym_lbl)

        # 年龄
        if age_sec > 0:
            age_lbl = QLabel(self._fmt_age(age_sec))
            age_lbl.setStyleSheet(
                f"color: {COLORS['text_mute']}; font-size: 11px; "
                f"background: {COLORS['bg_elev']}; padding: 2px 6px; border-radius: 3px;"
            )
            head.addWidget(age_lbl)

        if is_new:
            new_badge = QLabel("NEW")
            new_badge.setObjectName("badgeNew")
            head.addWidget(new_badge)

        if is_hot:
            hot_badge = QLabel("🔥 HOT")
            hot_badge.setObjectName("badgeHot")
            head.addWidget(hot_badge)

        head.addStretch()

        # 安全徽章
        safety_text = {
            "safe": ("✓ SAFE", "badgeSafe"),
            "warn": ("⚠ WARN", "badgeWarn"),
            "danger": ("✗ DANGER", "badgeDanger"),
            "unknown": ("? UNKNOWN", "badgeStopped"),
        }
        txt, obj = safety_text.get(self._safety, safety_text["unknown"])
        self.safety_badge = QLabel(txt)
        self.safety_badge.setObjectName(obj)
        head.addWidget(self.safety_badge)

        root.addLayout(head)

        # ========== Row 2: mint 地址 + 复制按钮 ==========
        addr_row = QHBoxLayout()
        addr_row.setSpacing(6)
        addr_lbl = QLabel(self._short_addr(self.mint))
        addr_lbl.setObjectName("tokenAddr")
        addr_row.addWidget(addr_lbl)

        copy_btn = QPushButton("📋")
        copy_btn.setFixedSize(22, 22)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setToolTip("复制地址")
        copy_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 0; "
            f"color: {COLORS['text_mute']}; font-size: 12px; }} "
            f"QPushButton:hover {{ color: {COLORS['accent']}; }}"
        )
        copy_btn.clicked.connect(self._on_copy_addr)
        addr_row.addWidget(copy_btn)

        chart_btn = QPushButton("📈")
        chart_btn.setFixedSize(22, 22)
        chart_btn.setCursor(Qt.PointingHandCursor)
        chart_btn.setToolTip("在 DEXScreener 查看")
        chart_btn.setStyleSheet(copy_btn.styleSheet())
        chart_btn.clicked.connect(self._on_open_chart)
        addr_row.addWidget(chart_btn)

        addr_row.addStretch()
        root.addLayout(addr_row)

        # ========== Row 3: 核心指标网格 ==========
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(16)
        metrics.setVerticalSpacing(4)

        # 价格
        self.price_lbl = QLabel(self._fmt_price(price_usd))
        self.price_lbl.setObjectName("tokenPrice")
        pr_label = QLabel("PRICE")
        pr_label.setObjectName("metricLabel")
        metrics.addWidget(pr_label, 0, 0)
        metrics.addWidget(self.price_lbl, 1, 0)

        # MCAP
        self.mcap_lbl = QLabel(self._fmt_num(mcap_usd))
        self.mcap_lbl.setObjectName("metricValue")
        mc_label = QLabel("MCAP")
        mc_label.setObjectName("metricLabel")
        metrics.addWidget(mc_label, 0, 1)
        metrics.addWidget(self.mcap_lbl, 1, 1)

        # Volume
        self.vol_lbl = QLabel(self._fmt_num(volume_24h))
        self.vol_lbl.setObjectName("metricValue")
        vl_label = QLabel("VOL 24H")
        vl_label.setObjectName("metricLabel")
        metrics.addWidget(vl_label, 0, 2)
        metrics.addWidget(self.vol_lbl, 1, 2)

        # Liquidity
        self.liq_lbl = QLabel(self._fmt_num(liquidity_usd))
        self.liq_lbl.setObjectName("metricValue")
        lq_label = QLabel("LIQ")
        lq_label.setObjectName("metricLabel")
        metrics.addWidget(lq_label, 0, 3)
        metrics.addWidget(self.liq_lbl, 1, 3)

        # Holders
        self.hold_lbl = QLabel(f"{holders:,}" if holders else "—")
        self.hold_lbl.setObjectName("metricValue")
        hd_label = QLabel("HOLDERS")
        hd_label.setObjectName("metricLabel")
        metrics.addWidget(hd_label, 0, 4)
        metrics.addWidget(self.hold_lbl, 1, 4)

        # Dev %
        dev_color = COLORS['danger'] if dev_percent > 10 else (COLORS['warn'] if dev_percent > 5 else COLORS['success'])
        self.dev_lbl = QLabel(f"{dev_percent:.1f}%" if dev_percent else "—")
        self.dev_lbl.setStyleSheet(
            f"font-family: 'Cascadia Mono', monospace; font-size: 13px; "
            f"font-weight: 600; color: {dev_color};"
        )
        dv_label = QLabel("DEV %")
        dv_label.setObjectName("metricLabel")
        metrics.addWidget(dv_label, 0, 5)
        metrics.addWidget(self.dev_lbl, 1, 5)

        root.addLayout(metrics)

        # Bonding 进度条（如果有）
        if progress >= 0:
            prog_row = QHBoxLayout()
            prog_row.setSpacing(6)
            prog_label = QLabel(f"Bonding {progress:.0f}%")
            prog_label.setStyleSheet(f"color: {COLORS['text_mute']}; font-size: 10px;")
            prog_row.addWidget(prog_label)

            # 简易进度条 (QFrame + gradient)
            bar_bg = QFrame()
            bar_bg.setFixedHeight(4)
            bar_bg.setStyleSheet(
                f"background: {COLORS['bg_elev']}; border-radius: 2px;"
            )
            bar_layout = QHBoxLayout(bar_bg)
            bar_layout.setContentsMargins(0, 0, 0, 0)
            bar_layout.setSpacing(0)

            fill = QFrame()
            fill_color = COLORS['accent2'] if progress < 95 else COLORS['success']
            fill.setStyleSheet(
                f"background: {fill_color}; border-radius: 2px;"
            )
            # 宽度按比例（用 stretch 模拟）
            bar_layout.addWidget(fill, int(progress * 10))
            spacer = QFrame()
            spacer.setStyleSheet("background: transparent;")
            bar_layout.addWidget(spacer, int((100 - progress) * 10))

            prog_row.addWidget(bar_bg, 1)
            root.addLayout(prog_row)

        # ========== Row 4: 快捷金额按钮 ==========
        presets = self._get_presets()
        unit = self._native_unit()

        amt_row = QHBoxLayout()
        amt_row.setSpacing(6)

        amt_lbl = QLabel("AMT:")
        amt_lbl.setObjectName("metricLabel")
        amt_row.addWidget(amt_lbl)

        self._amt_group = QButtonGroup(self)
        self._amt_group.setExclusive(True)

        for amt in presets:
            btn = QuickAmountButton(amt, unit)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, v=amt: self._set_amount(v))
            self._amt_group.addButton(btn)
            amt_row.addWidget(btn)

        # 自定义金额输入
        self.custom_amt = QLineEdit()
        self.custom_amt.setObjectName("amountInput")
        self.custom_amt.setPlaceholderText("自定义")
        self.custom_amt.setMaximumWidth(90)
        self.custom_amt.setText(str(presets[1]))  # 默认第二个
        self.custom_amt.textEdited.connect(self._on_custom_amt_edit)
        amt_row.addWidget(self.custom_amt)

        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet(f"color: {COLORS['text_mute']}; font-size: 11px; font-weight: 600;")
        amt_row.addWidget(unit_lbl)

        amt_row.addStretch()
        root.addLayout(amt_row)

        # ========== Row 5: 滑点 + BUY / SELL ==========
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        slip_lbl = QLabel("SLIPPAGE:")
        slip_lbl.setObjectName("metricLabel")
        action_row.addWidget(slip_lbl)

        self.slip_input = QLineEdit()
        self.slip_input.setObjectName("amountInput")
        self.slip_input.setText("5")
        self.slip_input.setMaximumWidth(50)
        action_row.addWidget(self.slip_input)

        slip_pct = QLabel("%")
        slip_pct.setStyleSheet(f"color: {COLORS['text_mute']}; font-size: 11px;")
        action_row.addWidget(slip_pct)

        action_row.addStretch()

        # SELL 按钮组（50% / 100%）
        sell_50 = QPushButton("SELL 50%")
        sell_50.setObjectName("sellBtn")
        sell_50.setCursor(Qt.PointingHandCursor)
        sell_50.clicked.connect(lambda: self._on_sell(50))
        action_row.addWidget(sell_50)

        sell_100 = QPushButton("SELL 100%")
        sell_100.setObjectName("sellBtn")
        sell_100.setCursor(Qt.PointingHandCursor)
        sell_100.clicked.connect(lambda: self._on_sell(100))
        action_row.addWidget(sell_100)

        # BUY 大按钮
        buy_btn = QPushButton(f"⚡ BUY")
        buy_btn.setObjectName("buyBtn")
        buy_btn.setCursor(Qt.PointingHandCursor)
        buy_btn.setMinimumWidth(90)
        buy_btn.clicked.connect(self._on_buy)
        action_row.addWidget(buy_btn)

        root.addLayout(action_row)

    # ---------- 交互逻辑 ----------

    def _set_amount(self, amount: float) -> None:
        self.custom_amt.setText(str(amount))

    def _on_custom_amt_edit(self, text: str) -> None:
        # 用户手动输入时，取消所有快捷按钮的选中态
        for btn in self._amt_group.buttons():
            btn.setChecked(False)

    def _get_amount(self) -> float:
        try:
            return float(self.custom_amt.text().strip())
        except (ValueError, TypeError):
            return 0.0

    def _get_slippage_bps(self) -> int:
        try:
            pct = float(self.slip_input.text().strip())
            return int(pct * 100)
        except (ValueError, TypeError):
            return 500  # 默认 5%

    def _on_buy(self) -> None:
        amt = self._get_amount()
        if amt <= 0:
            self._flash_error(self.custom_amt)
            return
        self.buy_requested.emit(self.mint, amt, self._get_slippage_bps())

    def _on_sell(self, percent: int) -> None:
        self.sell_requested.emit(self.mint, percent, self._get_slippage_bps())

    def _on_copy_addr(self) -> None:
        QApplication.clipboard().setText(self.mint)
        QToolTip.showText(self.cursor().pos(), "✓ 已复制", self)

    def _on_open_chart(self) -> None:
        if self.chain == "solana":
            url = f"https://dexscreener.com/solana/{self.mint}"
        elif self.chain == "bsc":
            url = f"https://dexscreener.com/bsc/{self.mint}"
        else:
            url = f"https://dexscreener.com/ethereum/{self.mint}"
        webbrowser.open(url)

    def _flash_error(self, widget) -> None:
        """输入错误时闪红 300ms"""
        orig = widget.styleSheet()
        widget.setStyleSheet(
            f"QLineEdit {{ background: {COLORS['bg']}; border: 1px solid {COLORS['danger']};"
            f"border-radius: 6px; padding: 6px 8px; color: {COLORS['text_bright']}; }}"
        )
        QTimer.singleShot(400, lambda: widget.setStyleSheet(orig))

    # ---------- 外部更新接口 ----------

    def update_price(self, price_usd: float) -> None:
        self.price_lbl.setText(self._fmt_price(price_usd))

    def update_metrics(self, mcap: float = None, vol: float = None,
                       liq: float = None, holders: int = None, dev: float = None) -> None:
        if mcap is not None: self.mcap_lbl.setText(self._fmt_num(mcap))
        if vol is not None: self.vol_lbl.setText(self._fmt_num(vol))
        if liq is not None: self.liq_lbl.setText(self._fmt_num(liq))
        if holders is not None: self.hold_lbl.setText(f"{holders:,}")
        if dev is not None:
            color = COLORS['danger'] if dev > 10 else (COLORS['warn'] if dev > 5 else COLORS['success'])
            self.dev_lbl.setText(f"{dev:.1f}%")
            self.dev_lbl.setStyleSheet(
                f"font-family: 'Cascadia Mono', monospace; font-size: 13px; "
                f"font-weight: 600; color: {color};"
            )

    # ---------- 工具方法 ----------

    def _get_presets(self) -> list:
        if self.chain == "solana": return self.PRESET_AMOUNTS_SOL
        if self.chain == "bsc": return self.PRESET_AMOUNTS_BNB
        return self.PRESET_AMOUNTS_ETH

    def _native_unit(self) -> str:
        return {"solana": "SOL", "bsc": "BNB", "ethereum": "ETH"}.get(self.chain, "USD")

    @staticmethod
    def _short_addr(addr: str) -> str:
        if len(addr) > 20:
            return f"{addr[:6]}...{addr[-6:]}"
        return addr

    @staticmethod
    def _fmt_price(p: float) -> str:
        if p <= 0: return "—"
        if p < 1e-8: return f"${p:.2e}"
        if p < 0.001: return f"${p:.8f}"
        if p < 1: return f"${p:.6f}"
        return f"${p:,.4f}"

    @staticmethod
    def _fmt_num(n: float) -> str:
        if not n or n <= 0: return "—"
        if n >= 1_000_000_000: return f"${n/1e9:.2f}B"
        if n >= 1_000_000: return f"${n/1e6:.2f}M"
        if n >= 1_000: return f"${n/1e3:.2f}K"
        return f"${n:,.0f}"

    @staticmethod
    def _fmt_age(sec: int) -> str:
        if sec < 60: return f"{sec}s"
        if sec < 3600: return f"{sec//60}m"
        if sec < 86400: return f"{sec//3600}h"
        return f"{sec//86400}d"
