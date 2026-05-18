"""
套利策略引擎 —— 核心决策逻辑

职责：
  1. 比较 CEX vs DEX 价差
  2. 计算扣除 Gas/手续费后的净利润
  3. 判断是否值得执行
  4. 生成套利信号 (ArbSignal)

支持的套利类型：
  - CEX 买 + DEX 卖（CEX 价低 → 链上价高）
  - DEX 买 + CEX 卖（链上价低 → CEX 价高）
  - 三角套利（A→B→C→A）
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from core.logger import logger
from .price_feed import PriceQuote


# ---------- 数据结构 ----------

@dataclass
class GasEstimate:
    """Gas 成本估算"""
    chain: str
    gas_price_gwei: Decimal = Decimal(0)
    gas_limit: int = 300_000
    native_price_usd: Decimal = Decimal(0)

    @property
    def cost_usd(self) -> Decimal:
        """Gas 成本（美元）"""
        gas_eth = self.gas_price_gwei * Decimal(self.gas_limit) / Decimal(10 ** 9)
        return gas_eth * self.native_price_usd


@dataclass
class ArbOpportunity:
    """套利机会"""
    pair: str                   # 交易对，如 "ETH/USDT"
    chain: str                  # 链上端所在链
    token_address: str          # 代币地址

    buy_source: str             # 买入端："binance" / "dex_ethereum" 等
    sell_source: str            # 卖出端
    buy_price: Decimal          # 买入价（ask）
    sell_price: Decimal         # 卖出价（bid）

    spread_pct: Decimal         # 价差百分比
    gross_profit_usd: Decimal   # 毛利润（不扣费）
    net_profit_usd: Decimal     # 净利润（扣除所有费用）

    gas_cost_usd: Decimal = Decimal(0)      # 链上 Gas
    cex_fee_usd: Decimal = Decimal(0)       # CEX 手续费
    slippage_cost_usd: Decimal = Decimal(0) # 滑点损失估算

    amount_usd: Decimal = Decimal(0)        # 建议交易金额
    confidence: float = 0.0                 # 置信度 0~1
    timestamp: float = 0.0

    @property
    def direction(self) -> str:
        """套利方向"""
        if "dex" in self.buy_source:
            return "DEX_BUY_CEX_SELL"
        else:
            return "CEX_BUY_DEX_SELL"

    @property
    def is_profitable(self) -> bool:
        return self.net_profit_usd > 0


@dataclass
class ArbConfig:
    """套利引擎配置"""
    # 最小价差阈值（百分比）
    min_spread_pct: Decimal = Decimal("0.3")
    # 最小净利润（美元）
    min_profit_usd: Decimal = Decimal("2.0")
    # 单次最大交易金额
    max_trade_usd: Decimal = Decimal("500")
    # 单次最小交易金额
    min_trade_usd: Decimal = Decimal("50")
    # CEX 手续费率（Maker/Taker 平均）
    cex_fee_rate: Decimal = Decimal("0.001")  # 0.1%
    # DEX 滑点估算
    dex_slippage_pct: Decimal = Decimal("0.3")  # 0.3%
    # 最大 Gas 价格（Gwei），超过不执行
    max_gas_gwei: Decimal = Decimal("50")
    # 执行超时（秒）
    execution_timeout: int = 30
    # 最大同时套利笔数
    max_concurrent: int = 3
    # 冷却时间（同一对不重复套利的间隔秒数）
    cooldown_seconds: int = 10


# ---------- 引擎 ----------

class ArbitrageEngine:
    """
    套利计算引擎

    用法：
        engine = ArbitrageEngine(config)
        opp = engine.evaluate(cex_quotes, dex_quote, gas_est)
        if opp and opp.is_profitable:
            executor.execute(opp)
    """

    def __init__(self, config: ArbConfig):
        self.config = config
        self._cooldowns: dict[str, float] = {}  # pair -> last_exec_time
        self._active_count = 0

    def evaluate(
        self,
        cex_quotes: list[PriceQuote],
        dex_quote: Optional[PriceQuote],
        gas_estimate: GasEstimate,
        trade_amount_usd: Optional[Decimal] = None,
    ) -> Optional[ArbOpportunity]:
        """
        评估一个交易对的套利机会。

        逻辑：
        1. 找 CEX 最优报价
        2. 与 DEX 报价比较
        3. 扣除费用后判断是否有利可图
        """
        if not cex_quotes or not dex_quote:
            return None

        if dex_quote.mid == 0:
            return None

        # 冷却检查
        pair_key = dex_quote.pair
        now = time.time()
        if pair_key in self._cooldowns:
            if now - self._cooldowns[pair_key] < self.config.cooldown_seconds:
                return None

        # 并发限制
        if self._active_count >= self.config.max_concurrent:
            return None

        # Gas 成本超标检查
        if gas_estimate.gas_price_gwei > self.config.max_gas_gwei:
            logger.debug(f"[ArbEngine] gas too high: {gas_estimate.gas_price_gwei} gwei")
            return None

        # 找 CEX 最佳报价
        best_cex_buy = min(cex_quotes, key=lambda q: q.ask)   # CEX 最低卖价（我们的买入价）
        best_cex_sell = max(cex_quotes, key=lambda q: q.bid)  # CEX 最高买价（我们的卖出价）

        # 两个方向的机会：
        # 方向 A: DEX 买入（低）+ CEX 卖出（高）
        opp_a = self._calc_opportunity(
            buy_quote=dex_quote,
            sell_quote=best_cex_sell,
            gas_estimate=gas_estimate,
            trade_amount_usd=trade_amount_usd,
            direction="DEX_BUY_CEX_SELL",
        )

        # 方向 B: CEX 买入（低）+ DEX 卖出（高）
        opp_b = self._calc_opportunity(
            buy_quote=best_cex_buy,
            sell_quote=dex_quote,
            gas_estimate=gas_estimate,
            trade_amount_usd=trade_amount_usd,
            direction="CEX_BUY_DEX_SELL",
        )

        # 选择更优的机会
        candidates = [o for o in [opp_a, opp_b] if o and o.is_profitable]
        if not candidates:
            return None

        best = max(candidates, key=lambda o: o.net_profit_usd)

        # 最终过滤
        if best.spread_pct < self.config.min_spread_pct:
            return None
        if best.net_profit_usd < self.config.min_profit_usd:
            return None

        return best

    def _calc_opportunity(
        self,
        buy_quote: PriceQuote,
        sell_quote: PriceQuote,
        gas_estimate: GasEstimate,
        trade_amount_usd: Optional[Decimal],
        direction: str,
    ) -> Optional[ArbOpportunity]:
        """计算单一方向的套利机会"""
        buy_price = buy_quote.ask   # 我们买入要付的价格
        sell_price = sell_quote.bid  # 我们卖出能得到的价格

        if buy_price <= 0 or sell_price <= 0:
            return None

        # 价差
        spread = sell_price - buy_price
        spread_pct = (spread / buy_price) * 100

        if spread_pct <= 0:
            return None

        # 交易金额
        amount = trade_amount_usd or self.config.max_trade_usd
        amount = min(amount, self.config.max_trade_usd)
        amount = max(amount, self.config.min_trade_usd)

        # 毛利润
        gross_profit = amount * spread_pct / 100

        # 费用计算
        gas_cost = gas_estimate.cost_usd
        cex_fee = amount * self.config.cex_fee_rate  # 单边手续费
        slippage_cost = amount * self.config.dex_slippage_pct / 100

        total_cost = gas_cost + cex_fee + slippage_cost
        net_profit = gross_profit - total_cost

        # 置信度：基于价差大小和流动性
        confidence = min(1.0, float(spread_pct) / 2.0)  # 1% 价差 = 0.5 置信度
        if buy_quote.liquidity_usd and buy_quote.liquidity_usd > amount * 10:
            confidence = min(1.0, confidence + 0.2)

        return ArbOpportunity(
            pair=buy_quote.pair or sell_quote.pair,
            chain=gas_estimate.chain,
            token_address="",  # 由调用方填充
            buy_source=buy_quote.source,
            sell_source=sell_quote.source,
            buy_price=buy_price,
            sell_price=sell_price,
            spread_pct=spread_pct,
            gross_profit_usd=gross_profit,
            net_profit_usd=net_profit,
            gas_cost_usd=gas_cost,
            cex_fee_usd=cex_fee,
            slippage_cost_usd=slippage_cost,
            amount_usd=amount,
            confidence=confidence,
            timestamp=time.time(),
        )

    def mark_executed(self, pair: str) -> None:
        """标记已执行，启动冷却"""
        self._cooldowns[pair] = time.time()
        self._active_count += 1

    def mark_completed(self, pair: str) -> None:
        """标记完成"""
        self._active_count = max(0, self._active_count - 1)

    def reset_cooldown(self, pair: str) -> None:
        """重置冷却"""
        self._cooldowns.pop(pair, None)
