"""把 loguru 的所有日志转发到 Qt 信号 → GUI 日志面板。

之前 scraper 的所有 logger.info / logger.warning 都只到 stderr，
而 EXE 是 console=False 的，用户根本看不到。这个桥让一切日志都进 GUI。
"""
from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QObject, Signal


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
        # 干掉 loguru 默认 sink（输出到 stderr），换成我们的
        logger.remove()
        # 注意：PyInstaller windowed EXE (console=False) 下 sys.stderr 是 None，
        # 给 loguru 加 None sink 会在每次 log 时抛 'NoneType' has no attribute 'write'。
        # 这就是导出时报错的根因。所以先校验再加。
        try:
            import sys
            if getattr(sys, "stderr", None) is not None and hasattr(sys.stderr, "write"):
                logger.add(sys.stderr, level="INFO", colorize=True,
                           format="{time:HH:mm:ss} | {level} | {message}")
        except Exception:
            pass
        logger.add(self._sink, level="DEBUG", format="{message}")

    def _sink(self, message) -> None:
        record = message.record
        try:
            level = record["level"].name
            msg = record["message"]
            self.log.emit(level, msg)
        except Exception:
            pass
