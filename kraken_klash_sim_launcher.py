"""
PyInstaller 入口
================

直接 import package 后调用 entry()，避免相对导入在 frozen 环境下的坑。
不在 package 内部，因为 PyInstaller 的 __main__.py 不识别 relative import。
"""
import sys

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
