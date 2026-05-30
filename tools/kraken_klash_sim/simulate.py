"""
蒙特卡洛模拟器（B）
==================

run_session：模拟一次完整的游戏会话（一直打到爆仓 / 达到目标 / 局数耗尽）
monte_carlo：跑 N 次 session，汇总统计

输出指标：
- mean / median / p5 / p95 final bankroll
- 破产率 (P(ruin))
- 平均总下注量（≈ Kraken Favor 累积量）
- 含空投后的"有效净收益"
"""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field
from typing import List, Optional

from .engine import BetSpec, play_round
from .strategies import Strategy, FixedFraction, Kelly


@dataclass
class SessionResult:
    final_bankroll: float
    rounds_played: int
    total_wagered: float          # 累计花掉的 Gobloonz（= Kraken Favor）
    ruined: bool
    hit_target: bool


@dataclass
class MonteCarloStats:
    n_sessions: int
    mean_final: float
    median_final: float
    p5_final: float
    p95_final: float
    ruin_rate: float
    mean_total_wagered: float
    mean_rounds: int
    # 含空投后的"等效价值"（按 gobloon_per_bcn 折算回 Gobloon 单位）
    mean_effective_value: float
    raw_finals: List[float] = field(default_factory=list)


# ---------- 单次会话 ----------
def run_session(
    bet: BetSpec,
    strategy: Strategy,
    start_bankroll: float,
    max_rounds: int,
    target_bankroll: Optional[float],
    rng: random.Random,
) -> SessionResult:
    bankroll = float(start_bankroll)
    total_wagered = 0.0
    last_outcome: Optional[float] = None
    rounds = 0
    strategy.reset()

    for rounds in range(1, max_rounds + 1):
        if bankroll <= 0:
            break
        if target_bankroll is not None and bankroll >= target_bankroll:
            break

        # 拿到策略想下的"单位数 / 资金"
        raw = strategy.next_units(bankroll, last_outcome)
        # 资金类策略（FixedFraction、Kelly）返回的是"想下多少 Gobloon"，要除以 cost 转 units
        if isinstance(strategy, (FixedFraction, Kelly)):
            units = raw / bet.cost
        else:
            units = raw

        # 截断：不能超过当前可用资金
        max_units = bankroll / bet.cost
        units = min(units, max_units)
        if units <= 0:
            last_outcome = 0.0
            continue

        stake = units * bet.cost
        outcome = play_round(bet, units, rng)
        bankroll += outcome
        total_wagered += stake
        last_outcome = outcome

    return SessionResult(
        final_bankroll=max(0.0, bankroll),
        rounds_played=rounds,
        total_wagered=total_wagered,
        ruined=bankroll <= 0,
        hit_target=target_bankroll is not None and bankroll >= target_bankroll,
    )


# ---------- 蒙特卡洛 ----------
def monte_carlo(
    bet: BetSpec,
    strategy: Strategy,
    *,
    start_bankroll: float,
    max_rounds: int,
    num_sessions: int,
    target_bankroll: Optional[float] = None,
    seed: Optional[int] = None,
    airdrop_bonus_per_gobloon: float = 0.0,
) -> MonteCarloStats:
    """
    跑 num_sessions 次会话。每次用独立的 rng（同种子可复现）。
    """
    base_rng = random.Random(seed)
    finals: List[float] = []
    wagered: List[float] = []
    rounds: List[int] = []
    ruined = 0

    for i in range(num_sessions):
        rng = random.Random(base_rng.random())
        r = run_session(bet, strategy, start_bankroll, max_rounds, target_bankroll, rng)
        finals.append(r.final_bankroll)
        wagered.append(r.total_wagered)
        rounds.append(r.rounds_played)
        if r.ruined:
            ruined += 1

    finals_sorted = sorted(finals)
    n = len(finals_sorted)

    def pct(p: float) -> float:
        idx = max(0, min(n - 1, int(p * n)))
        return finals_sorted[idx]

    mean_wagered = statistics.fmean(wagered)
    mean_final = statistics.fmean(finals)
    # 等效价值 = 余额 + 累计花掉的 * 空投单位返还
    mean_effective = mean_final + mean_wagered * airdrop_bonus_per_gobloon

    return MonteCarloStats(
        n_sessions=n,
        mean_final=mean_final,
        median_final=statistics.median(finals),
        p5_final=pct(0.05),
        p95_final=pct(0.95),
        ruin_rate=ruined / n,
        mean_total_wagered=mean_wagered,
        mean_rounds=int(statistics.fmean(rounds)),
        mean_effective_value=mean_effective,
        raw_finals=finals,
    )


# ---------- 文本报告 ----------
def format_stats(stats: MonteCarloStats, start_bankroll: float) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"  蒙特卡洛 {stats.n_sessions:,} 次会话结果")
    lines.append("=" * 60)
    lines.append(f"  起始余额        : {start_bankroll:,.0f} Gobloonz")
    lines.append(f"  平均最终余额    : {stats.mean_final:,.1f}")
    lines.append(f"  中位数最终余额  : {stats.median_final:,.1f}")
    lines.append(f"  5%  分位（差）  : {stats.p5_final:,.1f}")
    lines.append(f"  95% 分位（好）  : {stats.p95_final:,.1f}")
    lines.append(f"  破产率          : {stats.ruin_rate*100:.2f}%")
    lines.append(f"  平均下注总量    : {stats.mean_total_wagered:,.1f}（≈ Kraken Favor）")
    lines.append(f"  平均局数        : {stats.mean_rounds}")
    lines.append("-" * 60)
    delta = stats.mean_effective_value - start_bankroll
    sign = "+" if delta >= 0 else ""
    lines.append(f"  含空投等效价值  : {stats.mean_effective_value:,.1f}  "
                 f"({sign}{delta:,.1f} vs 起始)")
    lines.append("=" * 60)
    return "\n".join(lines)


# ---------- ASCII 直方图 ----------
def histogram(values: List[float], bins: int = 30, width: int = 50) -> str:
    """终端友好的资金分布图，免装 matplotlib"""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return f"  全部集中在 {lo:.0f}\n"
    step = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = min(bins - 1, int((v - lo) / step))
        counts[idx] += 1
    peak = max(counts) or 1
    lines = ["  最终余额分布："]
    for i, c in enumerate(counts):
        bar = "█" * int(c / peak * width)
        lines.append(f"  {lo + i*step:>8.0f} | {bar} {c}")
    return "\n".join(lines)
