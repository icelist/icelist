"""
CLI 入口

交互模式（推荐）:
    python main.py

直接指定:
    python main.py --fn sol.pumpfun
    python main.py --fn bsc.pancake_v2 --live
    python main.py --list
"""
import asyncio
import random
import typer

from core.config import load_config
from core.logger import logger
from chains import get_client
from functions import REGISTRY as FN_REGISTRY, get_function
from ui.banner import show_banner
from ui.menu import pick_chain, pick_function, pick_mode, confirm_run
from ui.dashboard import Dashboard, run_with_dashboard


app = typer.Typer(add_completion=False, invoke_without_command=True)


@app.callback()
def main(
    ctx: typer.Context,
    fn: str = typer.Option(None, "--fn", "-f", help="功能代号，如 sol.pumpfun / bsc.pancake_v2"),
    live: bool = typer.Option(False, "--live", help="实盘开关（默认 DRY_RUN）"),
    list_all: bool = typer.Option(False, "--list", help="列出所有功能"),
    no_banner: bool = typer.Option(False, "--no-banner", help="跳过开场动画"),
):
    if ctx.invoked_subcommand is not None:
        return

    if list_all:
        _print_list()
        raise typer.Exit()

    if not no_banner:
        show_banner(typewriter=True)

    # 1) 确定 chain + fn_code
    if fn:
        if fn not in FN_REGISTRY:
            typer.echo(f"Unknown function: {fn}. Use --list to see available.")
            raise typer.Exit(code=1)
        chain = FN_REGISTRY[fn]["chain"]
        fn_code = fn
    else:
        try:
            chain = pick_chain()
            while True:
                fn_code = pick_function(chain)
                if fn_code == "__back__":
                    chain = pick_chain()
                    continue
                break
        except KeyboardInterrupt:
            typer.echo("\nCancelled.")
            raise typer.Exit()

    # 2) 模式
    cfg = load_config()
    if fn:
        dry_run = not live
    else:
        try:
            dry_run = pick_mode()
        except KeyboardInterrupt:
            typer.echo("\nCancelled.")
            raise typer.Exit()

    # 3) 确认
    if not fn:
        if not confirm_run(chain, fn_code, dry_run):
            typer.echo("Aborted.")
            raise typer.Exit()
    elif not dry_run:
        typer.confirm("⚠ LIVE mode. Real funds will move. Continue?", abort=True)

    # 4) 运行
    asyncio.run(_run(chain, fn_code, cfg, dry_run))


def _print_list():
    """命令行形式列出所有功能"""
    from rich.console import Console
    from rich.table import Table
    from rich import box
    from ui.theme import APP_THEME, CHAIN_COLORS, CHAIN_ICONS, CHAIN_DISPLAY, FN_ICONS

    console = Console(theme=APP_THEME)
    for chain in ["solana", "bsc", "ethereum"]:
        color = CHAIN_COLORS[chain]
        t = Table(title=f"{CHAIN_ICONS[chain]}  {CHAIN_DISPLAY[chain]}",
                  title_style=f"bold {color}", box=box.ROUNDED,
                  border_style=color)
        t.add_column("Code", style="bold cyan")
        t.add_column("Function", style="white")
        t.add_column("Type", width=10)
        t.add_column("Description", style="grey50")
        for fn in [f for f in FN_REGISTRY.values() if f["chain"] == chain]:
            icon = FN_ICONS.get(fn["category"], "•")
            t.add_row(fn["code"], fn["display"],
                      f"{icon} {fn['category']}", fn["desc"])
        console.print(t)


async def _run(chain: str, fn_code: str, cfg: dict, dry_run: bool) -> None:
    """启动仪表盘 + 策略协程"""
    client = get_client(chain, cfg)
    fn_inst = get_function(fn_code, client, cfg)
    fn_meta = FN_REGISTRY[fn_code]

    dash = Dashboard(chain, fn_code, fn_meta["display"], dry_run)
    dash.log(f"Initialized {fn_meta['display']}", "cyan")

    # 真实策略协程
    strat_task = asyncio.create_task(fn_inst.run(dry_run=dry_run))

    # 只要策略还没填实现，仪表盘需要自己产生假数据让动画看起来"活着"
    # 生产版本：策略直接调用 dash.push_signal / dash.log 推送真实事件
    demo_task = asyncio.create_task(_demo_feed(dash))

    try:
        await run_with_dashboard(dash, strat_task)
    finally:
        demo_task.cancel()
        try:
            await demo_task
        except asyncio.CancelledError:
            pass


async def _demo_feed(dash: Dashboard) -> None:
    """
    演示数据推送 —— 让 UI 在策略 stub 阶段也能动起来。
    实际接入真实逻辑后，应删除此函数，由策略内部调用 dash.push_* 接口。
    """
    demo_tokens = ["PEPE", "BONK", "WIF", "POPCAT", "BRETT", "MOG",
                   "MEW", "GOAT", "CHILLGUY", "PNUT", "AI16Z"]
    await asyncio.sleep(0.8)
    while True:
        dash.tick()
        await asyncio.sleep(random.uniform(0.3, 1.2))
        roll = random.random()
        if roll < 0.15:
            tok = random.choice(demo_tokens) + str(random.randint(100, 999))
            amt = random.uniform(10, 50)
            dash.push_signal(tok, "BUY", amt, "new_pair_detected")
            dash.log(f"[demo] detected new pool {tok}, size ${amt:.2f}", "cyan")
            if random.random() < 0.7:
                dash.stats["success"] += 1
                dash.push_position(tok, entry=random.uniform(0.0001, 0.01),
                                   current=random.uniform(0.0001, 0.01),
                                   size_usd=amt)
            else:
                dash.stats["failed"] += 1
                dash.log(f"[demo] {tok} failed safety check", "warn")
        elif roll < 0.25 and dash.positions:
            p = random.choice(dash.positions)
            p["current"] *= random.uniform(0.92, 1.15)
        elif roll < 0.30:
            dash.log("[demo] scanning mempool...", "muted")
        # 更新 PnL
        dash.stats["pnl_usd"] = sum(
            (p["current"] - p["entry"]) / p["entry"] * p["size_usd"]
            for p in dash.positions if p["entry"]
        )


if __name__ == "__main__":
    app()
