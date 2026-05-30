"""
命令行入口

用法:
    # 单看赔率分析（A）
    python -m tools.kraken_klash_sim ev --config tools/kraken_klash_sim/config.example.yaml

    # 跑模拟（B）
    python -m tools.kraken_klash_sim sim --bet single_tile --strategy flat
    python -m tools.kraken_klash_sim sim --bet half_board --strategy martingale --base-units 1 --cap-units 64
    python -m tools.kraken_klash_sim sim --bet single_tile --strategy kelly --factor 0.5

    # 全部策略横向对比
    python -m tools.kraken_klash_sim compare --bet single_tile
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
import yaml

from .engine import BetSpec
from .strategies import build_strategy
from .ev import analyze, format_report
from .simulate import monte_carlo, format_stats, histogram


app = typer.Typer(add_completion=False, help="Kraken Klash 离线模拟器（不连真服）")

DEFAULT_CONFIG = Path(__file__).parent / "config.example.yaml"


# ---------- 辅助 ----------
def _load(config_path: Path) -> dict:
    if not config_path.exists():
        typer.echo(f"配置不存在：{config_path}", err=True)
        raise typer.Exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _bets(cfg: dict) -> list[BetSpec]:
    return [BetSpec(**b) for b in cfg["bets"]]


def _airdrop_bonus(cfg: dict) -> float:
    a = cfg.get("airdrop", {}) or {}
    if not a.get("enabled"):
        return 0.0
    return float(a.get("bcn_per_gobloon_spent", 0.0)) * float(a.get("gobloon_per_bcn", 0.0))


def _pick_bet(bets: list[BetSpec], name: str) -> BetSpec:
    for b in bets:
        if b.name == name:
            return b
    typer.echo(f"找不到 bet '{name}'。可用：{[b.name for b in bets]}", err=True)
    raise typer.Exit(1)


# ---------- 子命令 ----------
@app.command("ev")
def cmd_ev(
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
):
    """[A] 分析每种押法的 EV / 庄家抽水 / 含空投有效 EV"""
    cfg = _load(config)
    bets = _bets(cfg)
    rows = analyze(bets, cfg.get("airdrop", {}) or {})
    typer.echo(format_report(rows))

    # 给出一句直白总结
    pos = [r for r in rows if r["effective_ev_pct"] > 0]
    if pos:
        best = max(pos, key=lambda r: r["effective_ev_pct"])
        typer.echo(f"\n👉 含空投后正 EV 的押法：{[r['name'] for r in pos]}")
        typer.echo(f"   最优：{best['name']}，含空投 EV ≈ {best['effective_ev_pct']:+.2f}%/注")
    else:
        typer.echo("\n👉 配置下所有押法的『含空投有效 EV』都 ≤ 0，长期下注必亏。")
        typer.echo("   要么提高空投预期 (bcn_per_gobloon_spent)，要么不要下注。")


@app.command("sim")
def cmd_sim(
    bet: str = typer.Option(..., "--bet", "-b", help="押法名称，见 config.bets"),
    strategy: str = typer.Option("flat", "--strategy", "-s",
                                  help="flat | martingale | anti_martingale | fixed_fraction | kelly"),
    units: float = typer.Option(1.0, "--units", help="flat 用：每注单位数"),
    base_units: float = typer.Option(1.0, "--base-units", help="(anti_)martingale 底注"),
    cap_units: float = typer.Option(64.0, "--cap-units", help="martingale 单注上限"),
    max_streak: int = typer.Option(3, "--max-streak", help="anti_martingale 连胜重置点"),
    fraction: float = typer.Option(0.02, "--fraction", help="fixed_fraction 比例"),
    factor: float = typer.Option(0.5, "--factor", help="kelly 半凯利因子"),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    show_hist: bool = typer.Option(True, "--hist/--no-hist"),
):
    """[B] 跑蒙特卡洛模拟"""
    cfg = _load(config)
    bets = _bets(cfg)
    chosen = _pick_bet(bets, bet)

    sim_cfg = cfg.get("simulation", {})
    air_bonus = _airdrop_bonus(cfg)

    strat_spec = {
        "type": strategy,
        "units": units,
        "base_units": base_units,
        "cap_units": cap_units,
        "max_streak": max_streak,
        "fraction": fraction,
        "factor": factor,
    }
    strat = build_strategy(strat_spec, chosen, airdrop_bonus=air_bonus)

    typer.echo(f"\nBet     : {chosen.name}  (p={chosen.win_prob}, payout={chosen.payout}x, "
               f"house_edge={chosen.house_edge*100:+.2f}%)")
    typer.echo(f"Strategy: {strategy}  spec={strat_spec}\n")

    stats = monte_carlo(
        chosen, strat,
        start_bankroll=sim_cfg.get("start_bankroll", 1000),
        max_rounds=sim_cfg.get("max_rounds", 500),
        num_sessions=sim_cfg.get("num_sessions", 10000),
        target_bankroll=sim_cfg.get("target_bankroll"),
        seed=sim_cfg.get("random_seed"),
        airdrop_bonus_per_gobloon=air_bonus,
    )
    typer.echo(format_stats(stats, sim_cfg.get("start_bankroll", 1000)))
    if show_hist:
        typer.echo(histogram(stats.raw_finals))


@app.command("compare")
def cmd_compare(
    bet: str = typer.Option(..., "--bet", "-b"),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
):
    """横向对比所有内置策略"""
    cfg = _load(config)
    bets = _bets(cfg)
    chosen = _pick_bet(bets, bet)
    sim_cfg = cfg.get("simulation", {})
    air_bonus = _airdrop_bonus(cfg)
    start = sim_cfg.get("start_bankroll", 1000)

    presets = [
        ("flat-1",            {"type": "flat", "units": 1}),
        ("flat-5",            {"type": "flat", "units": 5}),
        ("martingale-cap64",  {"type": "martingale", "base_units": 1, "cap_units": 64}),
        ("anti_martingale-3", {"type": "anti_martingale", "base_units": 1, "max_streak": 3}),
        ("fixed_fraction-2%", {"type": "fixed_fraction", "fraction": 0.02}),
        ("kelly-half",        {"type": "kelly", "factor": 0.5}),
    ]

    typer.echo(f"\nBet: {chosen.name}  (p={chosen.win_prob}, payout={chosen.payout}x, "
               f"house_edge={chosen.house_edge*100:+.2f}%)")
    typer.echo(f"起始 {start:,.0f} | {sim_cfg.get('max_rounds')} 局 | "
               f"{sim_cfg.get('num_sessions')} 次会话\n")

    typer.echo(f"{'策略':<22}{'平均余':>10}{'中位余':>10}{'P5':>10}"
               f"{'P95':>10}{'破产率':>9}{'下注量':>11}{'有效价值':>11}")
    typer.echo("-" * 95)
    for name, spec in presets:
        strat = build_strategy(spec, chosen, airdrop_bonus=air_bonus)
        s = monte_carlo(
            chosen, strat,
            start_bankroll=start,
            max_rounds=sim_cfg.get("max_rounds", 500),
            num_sessions=sim_cfg.get("num_sessions", 10000),
            target_bankroll=sim_cfg.get("target_bankroll"),
            seed=sim_cfg.get("random_seed"),
            airdrop_bonus_per_gobloon=air_bonus,
        )
        typer.echo(
            f"{name:<22}"
            f"{s.mean_final:>10.0f}"
            f"{s.median_final:>10.0f}"
            f"{s.p5_final:>10.0f}"
            f"{s.p95_final:>10.0f}"
            f"{s.ruin_rate*100:>8.1f}%"
            f"{s.mean_total_wagered:>11.0f}"
            f"{s.mean_effective_value:>11.0f}"
        )
    typer.echo("\n说明: '有效价值' = 平均余额 + 累计下注 × 空投单位返还。这才是你真正的收益指标。")


if __name__ == "__main__":
    app()
