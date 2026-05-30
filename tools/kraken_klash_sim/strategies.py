"""
下注尺度策略（bet sizing）
=========================

每个策略只负责回答一件事：「这一局应该下多少 units？」
它**不能**改变游戏本身的概率（那是数学定律），只能控制风险曲线。

约定：
- next_units(bankroll, last_outcome) -> float
  返回 0 表示这局不下注；返回 >0 表示下多少 units（一个 units = bet.cost）。
- 余额不足时，外层会自动截断到 bankroll // bet.cost。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .engine import BetSpec


class Strategy:
    name: str = "base"

    def reset(self) -> None:
        pass

    def next_units(self, bankroll: float, last_outcome: Optional[float]) -> float:
        raise NotImplementedError


# ---------- 1. 平注 ----------
@dataclass
class Flat(Strategy):
    """每局下固定单位数。最稳，长期 EV = 单注 EV * 局数"""
    units: float = 1.0
    name: str = "flat"

    def next_units(self, bankroll, last_outcome):
        return self.units


# ---------- 2. 马丁格尔 ----------
@dataclass
class Martingale(Strategy):
    """
    输了就翻倍下，赢一次回本 + 1 单位。
    - 优点：胜率 < 50% 也能"经常赢"
    - 致命：连黑会指数级烧光本金；触及最大注或资金上限就崩盘
    """
    base_units: float = 1.0
    cap_units: float = 64.0     # 最大单注上限（防止无穷翻倍）
    name: str = "martingale"
    _streak: int = field(default=0, init=False)

    def reset(self):
        self._streak = 0

    def next_units(self, bankroll, last_outcome):
        if last_outcome is None or last_outcome > 0:
            self._streak = 0
        else:
            self._streak += 1
        units = self.base_units * (2 ** self._streak)
        return min(units, self.cap_units)


# ---------- 3. 反马丁（Paroli） ----------
@dataclass
class AntiMartingale(Strategy):
    """赢了翻倍，连胜 N 次后回到底注。本质是"让利润奔跑"。"""
    base_units: float = 1.0
    max_streak: int = 3
    name: str = "anti_martingale"
    _streak: int = field(default=0, init=False)

    def reset(self):
        self._streak = 0

    def next_units(self, bankroll, last_outcome):
        if last_outcome is None or last_outcome <= 0:
            self._streak = 0
        else:
            self._streak += 1
            if self._streak > self.max_streak:
                self._streak = 0
        return self.base_units * (2 ** self._streak)


# ---------- 4. 固定比例 ----------
@dataclass
class FixedFraction(Strategy):
    """每局下当前余额的 f 比例。常用 0.01 ~ 0.05"""
    fraction: float = 0.02
    name: str = "fixed_fraction"

    def next_units(self, bankroll, last_outcome):
        # 注意：返回的是 units（cost 倍数），由调用方转换
        # 这里返回 bankroll * fraction 直接当作可下注的资金，外层除以 cost
        return max(0.0, bankroll * self.fraction)


# ---------- 5. 凯利公式 ----------
@dataclass
class Kelly(Strategy):
    """
    f* = (p*b - q*|loss|) / (b*|loss|)   —— 非对称收益的通用 Kelly

    含空投保底 air_bonus 时：
      win  净倍率 b    = payout/cost - 1 + air_bonus
      loss 净倍率 loss = -1 + air_bonus
    若 air_bonus ≥ 1 等价"无风险盈利"，直接 100% 推进（被外层资金限制截断）。

    用半凯利 (factor=0.5) 降低方差；满凯利波动太大。
    EV ≤ 0 时 f* ≤ 0 → 不下注。
    """
    bet: BetSpec = None             # type: ignore[assignment]
    factor: float = 0.5             # 半凯利
    airdrop_bonus: float = 0.0      # 每 Gobloon 花掉返还的等价 Gobloon 数
    name: str = "kelly"

    def _f_star(self) -> float:
        b = self.bet.payout / self.bet.cost - 1 + self.airdrop_bonus
        loss = -1 + self.airdrop_bonus  # 输的时候的净倍率
        if loss >= 0:
            return 1.0 * self.factor   # 输也赚钱 → 全押（外层会截断到资金上限）
        if b <= 0:
            return 0.0
        p = self.bet.win_prob
        q = 1 - p
        f = (p * b - q * (-loss)) / (b * (-loss))
        return max(0.0, f) * self.factor

    def next_units(self, bankroll, last_outcome):
        if self.bet is None:
            raise RuntimeError("Kelly 策略需要 bet 实例")
        return bankroll * self._f_star()


# ---------- 工厂 ----------
def build_strategy(spec: dict, bet: BetSpec, airdrop_bonus: float = 0.0) -> Strategy:
    """
    spec 示例：
      {"type": "flat", "units": 1}
      {"type": "martingale", "base_units": 1, "cap_units": 64}
      {"type": "kelly", "factor": 0.5}

    airdrop_bonus: 每 Gobloon 花掉的空投等价返还（仅 kelly 用得上）
    """
    t = spec.get("type", "flat")
    if t == "flat":
        return Flat(units=spec.get("units", 1.0))
    if t == "martingale":
        return Martingale(base_units=spec.get("base_units", 1.0),
                          cap_units=spec.get("cap_units", 64.0))
    if t == "anti_martingale":
        return AntiMartingale(base_units=spec.get("base_units", 1.0),
                              max_streak=spec.get("max_streak", 3))
    if t == "fixed_fraction":
        return FixedFraction(fraction=spec.get("fraction", 0.02))
    if t == "kelly":
        return Kelly(bet=bet,
                     factor=spec.get("factor", 0.5),
                     airdrop_bonus=airdrop_bonus)
    raise ValueError(f"未知策略类型：{t}")
