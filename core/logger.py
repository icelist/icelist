"""
统一日志
"""
import sys
from pathlib import Path
from loguru import logger

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger.remove()
logger.add(sys.stdout, level="INFO",
           format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <cyan>{name}</cyan> - {message}")
logger.add(LOG_DIR / "sniper.log", rotation="50 MB", retention="14 days", level="DEBUG")

__all__ = ["logger"]
