"""
全局热键
F1-F4: 填充快捷买入金额到当前聚焦的 TokenCard
Ctrl+B: 对最新信号一键买入
Ctrl+S: 清仓全部
Esc: 停止全部策略
"""
from __future__ import annotations
from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QKeySequence, QShortcut


class HotkeyManager(QObject):
    """
    注册到主窗口的全局热键
    """

    preset_amount_triggered = Signal(int)   # 0=preset1, 1=preset2, etc
    quick_buy_latest = Signal()
    sell_all = Signal()
    stop_all = Signal()

    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self._shortcuts = []

        # F1-F4 金额档位
        for i, key in enumerate([Qt.Key_F1, Qt.Key_F2, Qt.Key_F3, Qt.Key_F4]):
            s = QShortcut(QKeySequence(key), main_window)
            s.activated.connect(lambda idx=i: self.preset_amount_triggered.emit(idx))
            self._shortcuts.append(s)

        # Ctrl+B 一键买入最新信号
        s = QShortcut(QKeySequence("Ctrl+B"), main_window)
        s.activated.connect(self.quick_buy_latest.emit)
        self._shortcuts.append(s)

        # Ctrl+Shift+S 清仓
        s = QShortcut(QKeySequence("Ctrl+Shift+S"), main_window)
        s.activated.connect(self.sell_all.emit)
        self._shortcuts.append(s)

        # Esc 停止全部策略
        s = QShortcut(QKeySequence("Esc"), main_window)
        s.activated.connect(self.stop_all.emit)
        self._shortcuts.append(s)
