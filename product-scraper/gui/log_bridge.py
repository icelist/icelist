"""把 loguru 的所有日志转发到 Qt 信号 → GUI 日志面板.

PyInstaller windowed EXE 里 sys.stderr / sys.stdout 都可能是 None，
这里做了完整的防御。
"""
from __future__ import annotations

import sys

from loguru import logger
from PySide6.QtCore import QObject, Signal


def _stderr_is_writable() -> bool:
    """判断 sys.stderr 是否可写，避免 None.write 错误。"""
    try:
        s = getattr(sys, "stderr", None)
        return s is not None and hasattr(s, "write") and callable(s.write)
    except Exception:
        return False


class LogBridge(QObject):
    """单例。LogBridge.instance().log 信号会发出每一条 loguru 记录。"""

    log = Signal(str, str)  # level, message

    _instance: "LogBridge | None" = None

    @classmethod
    def instance(cls) -> "LogBridge":
        if cls._instance is None:
            cls._instance = LogBridge()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        # 干掉 loguru 默认 sink
        try:
            logger.remove()
        except Exception:
            pass
        # 只有 stderr 可写时才加（PyInstaller windowed EXE 是 None）
        if _stderr_is_writable():
            try:
                logger.add(sys.stderr, level="INFO", colorize=True,
                           format="{time:HH:mm:ss} | {level} | {message}")
            except Exception:
                pass
        # GUI sink
        try:
            logger.add(self._sink, level="DEBUG", format="{message}",
                       backtrace=False, diagnose=False, catch=True)
        except Exception:
            pass

    def _sink(self, message) -> None:
        try:
            record = message.record
            level = record["level"].name
            msg = record["message"]
            self.log.emit(level, msg)
        except Exception:
            # sink 自己绝不能抛错，否则 loguru 会循环报错
            pass
