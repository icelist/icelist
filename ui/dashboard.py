"""
运行时动画仪表盘 —— rich.Live + Layout

布局：
┌─────────────────────────────────────────────┐
│               Header (banner)               │
├────────────────────┬────────────────────────┤
│  Latest Signals    │    Active Positions    │
│  (rolling table)   │    (positions table)   │
├────────────────────┴────────────────────────┤
│              Live Log Stream                │
├─────────────────────────────────────────────┤
│         Footer (stats + controls)           │
└─────────────────────────────────────────────┘
"""
import asyncio
import time
from collections import deque
from datetime import datetime
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.spinner import Spinner
from rich import box

from .theme import APP_THEME, CHAIN_COLORS, CHAIN_ICONS, CHAIN_DISPLAY


console = Console(theme=APP_THEME)


class Dashboard:
    """运行时仪表盘，提供给策略推送事件 -> 自动更新"""

    MAX_SIGNALS = 12
    MAX_LOGS = 10

    def __init__(self, chain: str, fn_code: str, fn_display: str, dry_run: bool):
        self.chain = chain
        self.fn_code = fn_code
        self.fn_display = fn_display
        self.dry_run = dry_run
        self.color = CHAIN_COLORS[chain]
        self.start_ts = time.time()

        self.signals: deque = deque(maxlen=self.MAX_SIGNALS)
        self.positions: list[dict] = []
        self.logs: deque = deque(maxlen=self.MAX_LOGS)
        self.stats = {
            "scanned": 0,
            "triggered": 0,
            "success": 0,
            "failed": 0,
            "pnl_usd": 0.0,
        }

    # ---------- 外部推送接口 ----------

    def tick(self) -> None:
        self.stats["scanned"] += 1

    def push_signal(self, symbol: str, action: str, amount: float, note: str = "") -> None:
        self.signals.appendleft({
            "t": datetime.now().strftime("%H:%M:%S"),
            "symbol": symbol,
            "action": action,
            "amount": amount,
            "note": note,
        })
        self.stats["triggered"] += 1

    def push_position(self, symbol: str, entry: float, current: float, size_usd: float) -> None:
        self.positions.append({
            "symbol": symbol, "entry": entry, "current": current, "size_usd": size_usd,
        })

    def log(self, text: str, style: str = "white") -> None:
        self.logs.appendleft((datetime.now().strftime("%H:%M:%S"), text, style))

    # ---------- 渲染 ----------

    def _header(self) -> Panel:
        uptime = int(time.time() - self.start_ts)
        mode_txt = Text("🛡 DRY_RUN", style="bold green") if self.dry_run else Text("🔥 LIVE", style="bold red")
        g = Table.grid(expand=True, padding=(0, 1))
        g.add_column(ratio=3)
        g.add_column(ratio=2, justify="right")
        left = Text.assemble(
            (f"{CHAIN_ICONS[self.chain]}  ", self.color),
            (CHAIN_DISPLAY[self.chain], f"bold {self.color}"),
            ("   │   ", "grey50"),
            (self.fn_display, "bold bright_cyan"),
            ("   ", ""),
            (f"[{self.fn_code}]", "grey50"),
        )
        right = Text.assemble(
            (f"⏱ {uptime//3600:02d}:{(uptime%3600)//60:02d}:{uptime%60:02d}", "grey50"),
            ("   ", ""),
            mode_txt,
        )
        g.add_row(left, right)
        return Panel(g, border_style=self.color, box=box.HEAVY, padding=(0, 1))

    def _signals_panel(self) -> Panel:
        t = Table(box=box.SIMPLE_HEAD, expand=True, show_edge=False,
                  header_style=f"bold {self.color}")
        t.add_column("Time", style="grey50", width=8)
        t.add_column("Token", style="bold white")
        t.add_column("Act", width=5)
        t.add_column("Size", justify="right")
        t.add_column("Note", style="grey50")
        if not self.signals:
            t.add_row("", "[grey50 italic]等待新信号...[/]", "", "", "")
        else:
            for s in self.signals:
                act_style = "bold green" if s["action"] == "BUY" else "bold red"
                t.add_row(s["t"], s["symbol"],
                          f"[{act_style}]{s['action']}[/]",
                          f"${s['amount']:.2f}", s["note"])
        return Panel(t, title="[bold]📡 Latest Signals[/]",
                     border_style="cyan", box=box.ROUNDED)

    def _positions_panel(self) -> Panel:
        t = Table(box=box.SIMPLE_HEAD, expand=True, show_edge=False,
                  header_style="bold green")
        t.add_column("Token", style="bold white")
        t.add_column("Entry", justify="right")
        t.add_column("Now", justify="right")
        t.add_column("PnL %", justify="right")
        t.add_column("Size", justify="right")
        if not self.positions:
            t.add_row("[grey50 italic]无持仓[/]", "", "", "", "")
        else:
            for p in self.positions:
                pct = (p["current"] - p["entry"]) / p["entry"] * 100 if p["entry"] else 0
                style = "bold green" if pct >= 0 else "bold red"
                arrow = "▲" if pct >= 0 else "▼"
                t.add_row(p["symbol"], f"{p['entry']:.6f}", f"{p['current']:.6f}",
                          f"[{style}]{arrow} {pct:+.2f}%[/]", f"${p['size_usd']:.0f}")
        return Panel(t, title="[bold]💼 Active Positions[/]",
                     border_style="green", box=box.ROUNDED)

    def _logs_panel(self) -> Panel:
        content = Text()
        # 日志中 "muted" / "success" 等 shorthand 映射到 Rich 内置色
        style_map = {
            "muted": "grey50", "success": "bold green", "warn": "bold yellow",
            "error": "bold red", "info": "cyan", "accent": "bold bright_magenta",
            "money": "bold green", "loss": "bold red",
        }
        if not self.logs:
            content = Text("等待事件...", style="grey50 italic")
        else:
            for ts, msg, style in self.logs:
                content.append(f"{ts} ", style="grey50")
                content.append(f"{msg}\n", style=style_map.get(style, style))
        return Panel(content, title="[bold]📜 Live Stream[/]",
                     border_style="magenta", box=box.ROUNDED, height=self.MAX_LOGS + 2)

    def _footer(self) -> Panel:
        s = self.stats
        g = Table.grid(expand=True, padding=(0, 2))
        for _ in range(6):
            g.add_column(justify="center")
        spinner_cell = Spinner("dots", text=Text("scanning", style="grey50"))
        pnl_style = "bold green" if s["pnl_usd"] >= 0 else "bold red"
        g.add_row(
            spinner_cell,
            Text.assemble(("Scanned\n", "grey50"), (f"{s['scanned']}", "bold")),
            Text.assemble(("Triggered\n", "grey50"), (f"{s['triggered']}", "bold cyan")),
            Text.assemble(("Success\n", "grey50"), (f"{s['success']}", "bold green")),
            Text.assemble(("Failed\n", "grey50"), (f"{s['failed']}", "bold red")),
            Text.assemble(("P&L\n", "grey50"), (f"${s['pnl_usd']:+.2f}", pnl_style)),
        )
        controls = Text("[Ctrl+C] 退出  ·  [L] 日志  ·  [P] 暂停",
                        style="grey50", justify="center")
        return Panel(Group(g, Align.center(controls)),
                     border_style="grey50", box=box.ROUNDED)

    def render(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(self._header(), size=3, name="header"),
            Layout(name="middle"),
            Layout(self._logs_panel(), size=self.MAX_LOGS + 2, name="logs"),
            Layout(self._footer(), size=4, name="footer"),
        )
        layout["middle"].split_row(
            Layout(self._signals_panel()),
            Layout(self._positions_panel()),
        )
        return layout


async def run_with_dashboard(dash: Dashboard, task: asyncio.Task) -> None:
    """在后台策略协程跑的同时，前台用 rich.Live 刷新仪表盘"""
    with Live(dash.render(), console=console, refresh_per_second=8,
              screen=True, transient=False) as live:
        try:
            while not task.done():
                live.update(dash.render())
                await asyncio.sleep(0.15)
        except asyncio.CancelledError:
            pass
        finally:
            live.update(dash.render())
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
