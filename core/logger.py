"""
统一日志

关键修复：
- PyInstaller 的 --windowed 模式下，sys.stdout / sys.stderr 是 None，
  loguru 不能直接 add(None)，否则会崩溃。
- 日志目录要写到用户目录，exe 所在目录可能没权限（Program Files）。
"""
import os
import sys
from pathlib import Path
from loguru import logger


def _log_dir() -> Path:
    """日志目录放到用户主目录，确保有写权限"""
    # 打包后优先用 ~/.chain-sniper/logs
    base = Path.home() / ".chain-sniper" / "logs"
    try:
        base.mkdir(parents=True, exist_ok=True)
        return base
    except Exception:
        # 退回到临时目录
        import tempfile
        tmp = Path(tempfile.gettempdir()) / "chain-sniper-logs"
        tmp.mkdir(parents=True, exist_ok=True)
        return tmp


LOG_DIR = _log_dir()

# 移除默认 sink
logger.remove()

# 1) 控制台 sink —— 仅当 stdout/stderr 存在时才加（避免 windowed 模式崩溃）
_console_stream = sys.stderr if sys.stderr is not None else sys.stdout
if _console_stream is not None:
    try:
        logger.add(
            _console_stream,
            level="INFO",
            format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <cyan>{name}</cyan> - {message}",
            enqueue=False,
        )
    except Exception:
        # 如果还是失败（比如 stderr 是一个已关闭的 handle），静默跳过
        pass

# 2) 文件 sink —— 一定有
try:
    logger.add(
        LOG_DIR / "sniper.log",
        rotation="50 MB",
        retention="14 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {name} - {message}",
        encoding="utf-8",
        enqueue=True,  # 多线程/多进程安全
    )
except Exception as e:
    # 文件 sink 失败也不阻塞启动（极端情况下磁盘满等）
    print(f"WARN: failed to add file log sink: {e}", file=sys.stderr if sys.stderr else sys.stdout)


__all__ = ["logger", "LOG_DIR"]
