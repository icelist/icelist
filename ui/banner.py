"""
启动横幅 —— 渐变色 ASCII + 打字机动画
"""
import time
import random
from rich.console import Console
from rich.align import Align
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns

from .theme import APP_THEME, CHAIN_COLORS, CHAIN_ICONS, CHAIN_DISPLAY


console = Console(theme=APP_THEME)

ASCII = r"""
   ____ _   _    _    ___ _   _      ____  _   _ ___ ____  _____ ____  
  / ___| | | |  / \  |_ _| \ | |    / ___|| \ | |_ _|  _ \| ____|  _ \ 
 | |   | |_| | / _ \  | ||  \| |    \___ \|  \| || || |_) |  _| | |_) |
 | |___|  _  |/ ___ \ | || |\  |     ___) | |\  || ||  __/| |___|  _ < 
  \____|_| |_/_/   \_\___|_| \_|    |____/|_| \_|___|_|   |_____|_| \_\
"""


def _gradient_text(text: str, colors: list[str]) -> Text:
    """给多行文本加横向渐变"""
    lines = text.split("\n")
    out = Text()
    n = len(colors)
    for line in lines:
        if not line.strip():
            out.append("\n")
            continue
        for i, ch in enumerate(line):
            c = colors[int(i / max(len(line), 1) * (n - 1))]
            out.append(ch, style=c)
        out.append("\n")
    return out


def show_banner(typewriter: bool = True) -> None:
    """主横幅 + 打字机副标题"""
    console.clear()

    # 渐变 ASCII 标题：紫 → 洋红 → 青
    grad = ["bright_magenta", "magenta", "bright_red", "bright_yellow",
            "bright_cyan", "cyan", "bright_blue"]
    title = _gradient_text(ASCII, grad)
    console.print(Align.center(title))

    # 副标题（打字机效果）
    subtitle = "⚡  Multi-Chain Alpha Sniper Framework  ⚡"
    if typewriter:
        out = Text()
        for ch in subtitle:
            out.append(ch, style="bold bright_cyan")
            console.print(Align.center(out), end="\r")
            time.sleep(0.012 + random.uniform(0, 0.015))
        console.print()  # newline
    else:
        console.print(Align.center(Text(subtitle, style="bold bright_cyan")))

    # 链标识卡片
    cards = []
    for ch in ["solana", "bsc", "ethereum"]:
        card = Panel(
            Align.center(Text(
                f"{CHAIN_ICONS[ch]}  {CHAIN_DISPLAY[ch]}",
                style=f"bold {CHAIN_COLORS[ch]}",
            )),
            border_style=CHAIN_COLORS[ch],
            width=22,
            padding=(0, 1),
        )
        cards.append(card)
    console.print(Align.center(Columns(cards, padding=(0, 2))))
    console.print()
