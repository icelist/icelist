"""
EV / 庄家优势分析（A：拆解游戏数学）
=================================

输入一份赔率配置，输出每种押法的：
- 命中概率
- 公平赔率 vs 实际赔率
- 单位下注期望收益率 (%)
- 庄家抽水 (%)
- 含空投保底后的"有效 EV"
"""
from __future__ import annotations

from typing import List, Dict, Any

from .engine import BetSpec


def analyze(bets: List[BetSpec], airdrop: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    返回每个 bet 的分析行。空投保底加成 = bcn_per_gobloon_spent * gobloon_per_bcn
    含义：每花 1 Gobloon 期望能从空投里挣回多少 Gobloon 等价价值。
    """
    air_bonus_per_gobloon = 0.0
    if airdrop.get("enabled"):
        bcn = airdrop.get("bcn_per_gobloon_spent", 0.0)
        rate = airdrop.get("gobloon_per_bcn", 0.0)
        air_bonus_per_gobloon = bcn * rate

    rows = []
    for b in bets:
        ev = b.ev_per_unit
        rows.append({
            "name": b.name,
            "win_prob": b.win_prob,
            "payout": b.payout,
            "fair_payout": b.fair_payout,
            "ev_pct": ev * 100,                                  # 纯下注 EV
            "house_edge_pct": b.house_edge * 100,
            "airdrop_kicker_pct": air_bonus_per_gobloon * 100,
            "effective_ev_pct": (ev + air_bonus_per_gobloon) * 100,
            "verdict": _verdict(ev, ev + air_bonus_per_gobloon),
            "desc": b.desc,
        })
    return rows


def _verdict(raw_ev: float, eff_ev: float) -> str:
    """一句话结论"""
    if eff_ev > 0.005:
        return "✓ 含空投后正 EV，可考虑下注"
    if eff_ev > -0.01:
        return "≈ 接近盈亏平衡，靠空投兜底"
    if raw_ev < -0.05:
        return "✗ 高抽水，长期必亏"
    return "✗ 长期亏损"


def format_report(rows: List[Dict[str, Any]]) -> str:
    """生成纯文本报告（适合在终端 / 日志里看）"""
    lines = []
    lines.append("=" * 86)
    lines.append(f"{'押法':<16}{'命中率':>8}{'实际赔':>8}{'公平赔':>8}"
                 f"{'EV%':>8}{'抽水%':>8}{'空投+%':>8}{'有效EV%':>9}  说明")
    lines.append("-" * 86)
    for r in rows:
        lines.append(
            f"{r['name']:<16}"
            f"{r['win_prob']*100:>7.2f}%"
            f"{r['payout']:>8.2f}"
            f"{r['fair_payout']:>8.2f}"
            f"{r['ev_pct']:>+8.2f}"
            f"{r['house_edge_pct']:>+8.2f}"
            f"{r['airdrop_kicker_pct']:>+8.2f}"
            f"{r['effective_ev_pct']:>+9.2f}"
            f"  {r['verdict']}"
        )
    lines.append("=" * 86)
    return "\n".join(lines)
