"""
loguru → Qt Signal 桥接
"""
from PySide6.QtCore import QObject, Signal
from core.logger import logger


class LogBridge(QObject):
    message = Signal(str, str)  # level, message

    def __init__(self):
        super().__init__()
        # 注册 sink
        self._sink_id = logger.add(self._sink, level="DEBUG",
                                    format="{message}")

    def _sink(self, record) -> None:
        # loguru 传进来的是带元数据的 Message 对象
        try:
            msg = record.record["message"]
            level = record.record["level"].name
            name = record.record.get("name") or ""
            full = f"{name:<30} | {msg}" if name else msg
            self.message.emit(level, full)
        except Exception:
            pass

    def detach(self) -> None:
        try:
            logger.remove(self._sink_id)
        except Exception:
            pass
