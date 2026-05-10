"""
交互菜单 —— 链选择 / 功能选择 / 模式选择
使用 questionary 提供箭头键 + 搜索过滤
"""
import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich import box

from .theme import APP_THEME, CHAIN_COLORS, CHAIN_ICONS, CHAIN_DISPLAY, FN_ICONS
from functions import functions_for_chain


console = Console(theme=APP_THEME)

# questionary 主题（和 rich 风格对齐）
Q_STYLE = Style([
    ("qmark",       "fg:#ff79c6 bold"),
    ("question",    "fg:#8be9fd bold"),
    ("answer",      "fg:#50fa7b bold"),
    ("pointer",     "fg:#ff79c6 bold"),
    ("highlighted", "fg:#bd93f9 bold"),
    ("selected",    "fg:#50fa7b"),
    ("separator",   "fg:#6272a4"),
    ("instruction", "fg:#6272a4 italic"),
    ("text",        ""),
    ("disabled",    "fg:#6272a4 italic"),
])


def pick_chain() -> str:
    """选择链"""
    console.print(Panel(
        Align.center("[bold bright_cyan]Step 1[/] · 选择链 (Chain)"),
        border_style="bright_cyan", box=box.ROUNDED, padding=(0, 2),
    ))

    choices = [
        questionary.Choice(
            title=f"{CHAIN_ICONS[c]}  {CHAIN_DISPLAY[c]:<12}  — {desc}",
            value=c,
        )
        for c, desc in [
            ("solana",   "Pump.fun / Raydium / Meteora · 高频 memecoin 主战场"),
            ("bsc",      "PancakeSwap V2/V3 / Four.meme · 低 gas 土狗"),
            ("ethereum", "Uniswap V2/V3 / Virtuals · 大市值 / 机构"),
        ]
    ]
    result = questionary.select(
        "Select chain →",
        choices=choices,
        style=Q_STYLE,
        qmark="❯",
        pointer="▶",
    ).ask()
    if result is None:
        raise KeyboardInterrupt
    return result


def pick_function(chain: str) -> str:
    """选择功能（按链过滤）"""
    color = CHAIN_COLORS[chain]
    console.print()
    console.print(Panel(
        Align.center(
            f"[bold {color}]Step 2[/] · 选择功能 "
            f"({CHAIN_ICONS[chain]} {CHAIN_DISPLAY[chain]})"
        ),
        border_style=color, box=box.ROUNDED, padding=(0, 2),
    ))

    fns = functions_for_chain(chain)

    # 先展示功能卡片
    tbl = Table(box=box.SIMPLE_HEAVY, show_header=True,
                header_style=f"bold {color}", border_style="grey50")
    tbl.add_column("#", style="grey50", width=3)
    tbl.add_column("Code", style="bold cyan")
    tbl.add_column("功能", style="white")
    tbl.add_column("类型", width=10)
    tbl.add_column("说明", style="grey50")
    for i, fn in enumerate(fns, 1):
        icon = FN_ICONS.get(fn["category"], "•")
        tbl.add_row(str(i), fn["code"], fn["display"],
                    f"{icon} {fn['category']}", fn["desc"])
    console.print(tbl)
    console.print()

    choices = [
        questionary.Choice(
            title=f"{FN_ICONS.get(fn['category'], '•')}  {fn['display']:<22}  [{fn['code']}]",
            value=fn["code"],
        )
        for fn in fns
    ]
    choices.append(questionary.Separator())
    choices.append(questionary.Choice(title="← 返回上一级", value="__back__"))

    result = questionary.select(
        "Select function →",
        choices=choices,
        style=Q_STYLE,
        qmark="❯",
        pointer="▶",
    ).ask()
    if result is None:
        raise KeyboardInterrupt
    return result


def pick_mode() -> bool:
    """选择运行模式，返回 dry_run 布尔值"""
    console.print()
    console.print(Panel(
        Align.center("[bold yellow]Step 3[/] · 选择运行模式"),
        border_style="yellow", box=box.ROUNDED, padding=(0, 2),
    ))
    choice = questionary.select(
        "Mode →",
        choices=[
            questionary.Choice(
                title="🛡  DRY_RUN   (安全模式：只检测 + 通知，不真实下单)",
                value="dry",
            ),
            questionary.Choice(
                title="🔥  LIVE      (实盘模式：会真实花钱，需再次确认)",
                value="live",
            ),
        ],
        style=Q_STYLE, qmark="❯", pointer="▶",
    ).ask()
    if choice is None:
        raise KeyboardInterrupt

    if choice == "live":
        confirm = questionary.confirm(
            "⚠  真的要开启实盘吗？这会动用钱包中的真实资金",
            default=False, style=Q_STYLE, qmark="❯",
        ).ask()
        if not confirm:
            return True  # 返回 dry_run
    return choice == "dry"


def confirm_run(chain: str, fn_code: str, dry_run: bool) -> bool:
    """最终确认面板"""
    from functions import REGISTRY
    fn = REGISTRY[fn_code]
    color = CHAIN_COLORS[chain]

    body = Table.grid(padding=(0, 2))
    body.add_column(style="grey50", justify="right")
    body.add_column(style="bold white")
    body.add_row("Chain:",    f"[{color}]{CHAIN_ICONS[chain]} {CHAIN_DISPLAY[chain]}[/]")
    body.add_row("Function:", f"[bold cyan]{fn['display']}[/] [grey50]({fn_code})[/]")
    body.add_row("Category:", f"{FN_ICONS.get(fn['category'], '•')} {fn['category']}")
    body.add_row("Mode:",     "[bold green]🛡 DRY_RUN[/]" if dry_run else "[bold red]🔥 LIVE[/]")
    body.add_row("Desc:",     f"[grey50]{fn['desc']}[/]")

    console.print()
    console.print(Panel(
        body, title="[bold]确认启动参数[/]",
        border_style=color, box=box.DOUBLE, padding=(1, 2),
    ))

    ok = questionary.confirm(
        "启动？", default=True, style=Q_STYLE, qmark="❯",
    ).ask()
    return bool(ok)
