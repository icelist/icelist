"""
PyInstaller 入口
================

直接 import package 后调用 entry()，避免相对导入在 frozen 环境下的坑。
不在 package 内部，因为 PyInstaller 的 __main__.py 不识别 relative import。
"""
import sys

# Windows 控制台默认 cp1252，会让中文报 UnicodeEncodeError。
# Python 3.7+ 支持 reconfigure，先把 stdout/stderr 切到 UTF-8。
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from tools.kraken_klash_sim.cli import app
from tools.kraken_klash_sim.play import main as play_main


def entry() -> None:
    # 没参数时默认进交互模式（exe 双击场景）
    if len(sys.argv) <= 1:
        play_main()
        return
    app()


if __name__ == "__main__":
    entry()
