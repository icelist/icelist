"""
交互式单机版 —— 纯娱乐用
======================

特点：
- 完全离线，不连任何服务器，不涉及真钱
- 用 rich 渲染彩色 TUI；questionary 做选项菜单
- 会话历史保存在 ~/.kraken_klash_sim/sessions.jsonl
- 也支持「快进自动跑 N 局」模式

启动:
    python -m tools.kraken_klash_sim play
    或双击打包后的 KrakenKlashSim.exe
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import questionary
import yaml
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .engine import BetSpec, play_round


# ---------- 数据 ----------
DEFAULT_CONFIG = Path(__file__).parent / "config.example.yaml"
SAVE_DIR = Path.home() / ".kraken_klash_sim"
SAVE_FILE = SAVE_DIR / "sessions.jsonl"


@dataclass
class GameState:
    bankroll: float
    starting_bankroll: float
    kraken_favor: float = 0.0
    rounds: int = 0
    wins: int = 0
    losses: int = 0
    streak: int = 0          # 正 = 连胜，负 = 连黑
    biggest_win: float = 0.0
    biggest_loss: float = 0.0
    history: List[dict] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def record(self, bet: BetSpec, units: float, outcome: float) -> None:
        stake = bet.cost * units
        self.kraken_favor += stake
        self.bankroll += outcome
        self.rounds += 1
        if outcome > 0:
            self.wins += 1
            self.streak = self.streak + 1 if self.streak >= 0 else 1
            self.biggest_win = max(self.biggest_win, outcome)
        else:
            self.losses += 1
            self.streak = self.streak - 1 if self.streak <= 0 else -1
            self.biggest_loss = min(self.biggest_loss, outcome)
        self.history.append({
            "round": self.rounds,
            "bet": bet.name,
            "units": units,
            "stake": stake,
            "outcome": outcome,
            "bankroll": self.bankroll,
        })

    def summary(self) -> dict:
        net = self.bankroll - self.starting_bankroll
        win_rate = self.wins / self.rounds if self.rounds else 0.0
        return {
            "started_at": self.started_at,
            "ended_at": datetime.now().isoformat(timespec="seconds"),
            "rounds": self.rounds,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(win_rate, 4),
            "starting_bankroll": self.starting_bankroll,
            "final_bankroll": self.bankroll,
            "net": net,
            "kraken_favor": self.kraken_favor,
            "biggest_win": self.biggest_win,
            "biggest_loss": self.biggest_loss,
        }


# ---------- 渲染 ----------
console = Console()


def banner() -> None:
    art = Text()
    art.append("\n  🐙  KRAKEN  KLASH  🐙\n", style="bold magenta")
    art.append("  ── Offline Simulator ──\n", style="dim cyan")
    art.append("  纯单机模拟 · 不连服务器 · 不涉真钱 · 仅供娱乐\n", style="dim")
    console.print(Panel(Align.center(art), border_style="magenta"))


def render_state(state: GameState) -> None:
    delta = state.bankroll - state.starting_bankroll
    delta_color = "green" if delta >= 0 else "red"
    streak_str = (f"🔥 连胜 {state.streak}" if state.streak > 1
                  else f"❄️  连黑 {-state.streak}" if state.streak < -1
                  else "—")

    t = Table.grid(padding=(0, 2))
    t.add_column(style="cyan", justify="right")
    t.add_column(style="bold")
    t.add_row("局数", f"{state.rounds}")
    t.add_row("当前余额", f"[{delta_color}]{state.bankroll:,.1f}[/] Gobloonz "
                          f"([{delta_color}]{delta:+,.1f}[/])")
    t.add_row("Kraken Favor", f"{state.kraken_favor:,.1f}")
    t.add_row("胜/负", f"{state.wins} / {state.losses}  "
                       f"({state.wins/max(1,state.rounds)*100:.1f}%)")
    t.add_row("当前势头", streak_str)
    console.print(Panel(t, title="状态", border_style="cyan", expand=False))


def render_bets(bets: List[BetSpec]) -> None:
    t = Table(title="可用押法", border_style="dim", show_header=True, header_style="bold magenta")
    t.add_column("名称")
    t.add_column("命中率", justify="right")
    t.add_column("赔率", justify="right")
    t.add_column("理论 EV", justify="right")
    t.add_column("说明")
    for b in bets:
        ev = b.ev_per_unit * 100
        ev_color = "green" if ev > 0 else "red"
        t.add_row(b.name, f"{b.win_prob*100:.2f}%", f"{b.payout:.2f}x",
                  f"[{ev_color}]{ev:+.2f}%[/]", b.desc)
    console.print(t)


def announce_roll(bet: BetSpec, units: float, outcome: float, rng: random.Random) -> None:
    """带一点动画感"""
    console.print()
    console.print("  🎲 [magenta]触手翻动了一下...[/]", end="")
    for _ in range(3):
        time.sleep(0.18)
        console.print("[magenta].[/]", end="")
    console.print()

    if outcome > 0:
        console.print(f"  ✅ [bold green]命中！[/] {bet.name} —— 赢得 [bold green]+{outcome:,.1f}[/] Gobloonz")
    else:
        console.print(f"  ❌ [bold red]未中[/] —— 失去 [bold red]{outcome:,.1f}[/] Gobloonz")
    console.print()


# ---------- 持久化 ----------
def save_session(summary: dict) -> Path:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    with open(SAVE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return SAVE_FILE


def load_history() -> List[dict]:
    if not SAVE_FILE.exists():
        return []
    out = []
    with open(SAVE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def show_history() -> None:
    rows = load_history()
    if not rows:
        console.print("[dim]还没有历史会话。[/]")
        return
    t = Table(title=f"历史会话 (共 {len(rows)} 次)", border_style="dim")
    for col in ("时间", "局数", "胜率", "起始", "结束", "净", "Favor"):
        t.add_column(col, justify="right" if col != "时间" else "left")
    for r in rows[-20:]:
        net_color = "green" if r["net"] >= 0 else "red"
        t.add_row(
            r["started_at"],
            str(r["rounds"]),
            f"{r['win_rate']*100:.1f}%",
            f"{r['starting_bankroll']:,.0f}",
            f"{r['final_bankroll']:,.0f}",
            f"[{net_color}]{r['net']:+,.0f}[/]",
            f"{r['kraken_favor']:,.0f}",
        )
    console.print(t)


# ---------- 主循环 ----------
def _ask_bet(bets: List[BetSpec]) -> Optional[BetSpec]:
    choices = [{"name": f"{b.name}  ({b.win_prob*100:.1f}% / {b.payout}x)", "value": b.name}
               for b in bets]
    choices += [
        questionary.Separator(),
        {"name": "📊  查看本场统计", "value": "__stat__"},
        {"name": "⚡  快进自动跑 N 局", "value": "__auto__"},
        {"name": "📜  查看历史会话", "value": "__hist__"},
        {"name": "💾  保存并退出", "value": "__quit__"},
    ]
    pick = questionary.select("选择动作:", choices=choices).ask()
    if pick is None or pick == "__quit__":
        return None
    if pick == "__stat__":
        return BetSpec(name="__stat__", cost=1, win_prob=0.5, payout=1)  # sentinel
    if pick == "__auto__":
        return BetSpec(name="__auto__", cost=1, win_prob=0.5, payout=1)
    if pick == "__hist__":
        return BetSpec(name="__hist__", cost=1, win_prob=0.5, payout=1)
    return next(b for b in bets if b.name == pick)


def _ask_units(state: GameState, bet: BetSpec) -> float:
    max_units = state.bankroll / bet.cost
    raw = questionary.text(
        f"押多少单位？(1 单位 = {bet.cost} Gobloonz; 当前可下最多 {max_units:.0f} 单位)",
        default="1",
        validate=lambda v: v.replace(".", "", 1).isdigit() and float(v) > 0,
    ).ask()
    if raw is None:
        return 0
    return min(float(raw), max_units)


def _auto_play(state: GameState, bets: List[BetSpec], rng: random.Random) -> None:
    bet_name = questionary.select(
        "快进押哪种？",
        choices=[b.name for b in bets],
    ).ask()
    if bet_name is None:
        return
    n_str = questionary.text("跑多少局？", default="100",
                             validate=lambda v: v.isdigit() and 1 <= int(v) <= 10000).ask()
    if n_str is None:
        return
    units_str = questionary.text("每局多少单位？", default="1",
                                 validate=lambda v: v.replace('.', '', 1).isdigit() and float(v) > 0).ask()
    if units_str is None:
        return

    bet = next(b for b in bets if b.name == bet_name)
    units = float(units_str)
    n = int(n_str)

    console.print(f"\n[yellow]⚡ 快进 {n} 局，每局 {units} 单位 {bet_name}...[/]")
    start_bank = state.bankroll
    ran = 0
    for _ in range(n):
        if state.bankroll < bet.cost * units:
            console.print("[red]余额不足，提前结束。[/]")
            break
        outcome = play_round(bet, units, rng)
        state.record(bet, units, outcome)
        ran += 1

    delta = state.bankroll - start_bank
    color = "green" if delta >= 0 else "red"
    console.print(f"[{color}]快进结束 → 实际跑了 {ran} 局，"
                  f"净 {delta:+,.1f}，当前余额 {state.bankroll:,.1f}[/]\n")


def play_loop(config_path: Path = DEFAULT_CONFIG, *,
              starting_bankroll: Optional[float] = None,
              seed: Optional[int] = None) -> None:
    """主交互循环"""
    if not config_path.exists():
        console.print(f"[red]配置不存在：{config_path}[/]")
        return
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    bets = [BetSpec(**b) for b in cfg["bets"]]
    if starting_bankroll is None:
        starting_bankroll = float(cfg.get("simulation", {}).get("start_bankroll", 1000))

    rng = random.Random(seed)
    state = GameState(bankroll=starting_bankroll, starting_bankroll=starting_bankroll)

    banner()
    console.print(f"[dim]起始余额 {starting_bankroll:,.0f} Gobloonz · "
                  f"配置: {config_path.name}[/]\n")
    render_bets(bets)
    console.print()

    while True:
        render_state(state)
        if state.bankroll < min(b.cost for b in bets):
            console.print("[bold red]💀 余额不足以继续下注，会话结束。[/]")
            break

        choice = _ask_bet(bets)
        if choice is None:
            break

        if choice.name == "__stat__":
            render_state(state)
            continue
        if choice.name == "__hist__":
            show_history()
            continue
        if choice.name == "__auto__":
            _auto_play(state, bets, rng)
            continue

        units = _ask_units(state, choice)
        if units <= 0:
            continue

        outcome = play_round(choice, units, rng)
        announce_roll(choice, units, outcome, rng)
        state.record(choice, units, outcome)

    # 收尾
    summary = state.summary()
    save_path = save_session(summary)
    console.print()
    console.print(Panel.fit(
        f"会话已保存到 [cyan]{save_path}[/]\n"
        f"局数 {summary['rounds']}  胜率 {summary['win_rate']*100:.1f}%  "
        f"净 [{'green' if summary['net']>=0 else 'red'}]{summary['net']:+,.1f}[/]  "
        f"Favor {summary['kraken_favor']:,.0f}",
        title="再见，玩家", border_style="magenta",
    ))


# ---------- 给打包后的 exe 用的入口 ----------
def main() -> None:
    """exe 双击启动时的入口（不带参数）"""
    try:
        play_loop()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]再见。[/]")
    except Exception as e:  # noqa: BLE001
        console.print_exception()
        console.print(f"\n[red]出错了: {e}[/]")
        # 打包后双击运行时不要立刻关掉窗口
        try:
            input("\n按 Enter 退出...")
        except EOFError:
            pass


if __name__ == "__main__":
    main()
