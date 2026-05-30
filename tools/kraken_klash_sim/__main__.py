"""
模块入口。
- `python -m tools.kraken_klash_sim`            → 直接进交互模式（双击 exe 也走这个）
- `python -m tools.kraken_klash_sim ev|sim|...` → CLI 子命令
"""
import sys

# Windows cp1252 终端 → UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from .cli import app
from .play import main as play_main


def entry() -> None:
    # 没传任何子命令时，进入交互模式（适合 exe 双击）
    if len(sys.argv) <= 1:
        play_main()
        return
    app()


if __name__ == "__main__":
    entry()
