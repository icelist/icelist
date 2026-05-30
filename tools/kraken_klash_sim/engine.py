"""
单局博弈引擎
===========
- BetSpec：一种下注方式的赔率定义
- play_round：模拟一局结果（命中 / 未命中）
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class BetSpec:
    """单一下注规则"""
    name: str
    cost: float           # 单注消耗（Gobloonz）
    win_prob: float       # 命中概率
    payout: float         # 命中时返还总额（含本金）
    desc: str = ""

    def __post_init__(self) -> None:
        if not 0.0 < self.win_prob <= 1.0:
            raise ValueError(f"win_prob 必须在 (0,1]：{self.win_prob}")
        if self.cost <= 0 or self.payout < 0:
            raise ValueError(f"cost / payout 不合法：cost={self.cost}, payout={self.payout}")

    # ---------- 核心数学 ----------
    @property
    def ev_per_unit(self) -> float:
        """每 1 单位下注的期望损益（净）。EV = p*payout - cost，再按 cost 归一化"""
        return (self.win_prob * self.payout - self.cost) / self.cost

    @property
    def house_edge(self) -> float:
        """庄家优势（>0 表示长期玩家亏）"""
        return -self.ev_per_unit

    @property
    def fair_payout(self) -> float:
        """达到 0 抽水时的赔率（用于对比庄家比公平赔率少给了多少）"""
        return self.cost / self.win_prob


def play_round(bet: BetSpec, units: float, rng: random.Random) -> float:
    """
    模拟一局结果。

    参数:
        bet:    下注规则
        units:  下注单位数（例如 1 倍 / 4 倍 / 16 倍，对应马丁加注）
        rng:    随机数生成器

    返回:
        净损益 = 命中时 +(payout-cost)*units，未命中 -cost*units
    """
    stake = bet.cost * units
    if rng.random() < bet.win_prob:
        return (bet.payout - bet.cost) * units
    return -stake
