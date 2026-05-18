"""
套利策略 —— 注册到 REGISTRY 的功能类

提供 3 种套利模式：
  1. ETH CEX-DEX 套利：ETH/USDT 在 Binance 和 Uniswap 之间套利
  2. BSC CEX-DEX 套利：BNB/USDT + BSC 热门代币套利
  3. SOL CEX-DEX 套利：SOL/USDT 在 Binance 和 Jupiter 之间套利
"""
from __future__ import annotations
import asyncio
from decimal import Decimal

from core.base import Strategy
from core.logger import logger
from core.notifier import notify
from chains import get_client

from .price_feed import PriceFeedAggregator, PriceQuote
from .engine import ArbitrageEngine, ArbConfig, GasEstimate, ArbOpportunity
from .executor import ArbitrageExecutor


# ---------- 交易对配置 ----------

# 每条链上可套利的交易对
ARB_PAIRS = {
    "ethereum": [
        {
            "pair": "ETH/USDT",
            "token_address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
            "is_native": True,
        },
        {
            "pair": "LINK/USDT",
            "token_address": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
            "is_native": False,
        },
        {
            "pair": "UNI/USDT",
            "token_address": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
            "is_native": False,
        },
        {
            "pair": "PEPE/USDT",
            "token_address": "0x6982508145454Ce325dDbE47a25d4ec3d2311933",
            "is_native": False,
        },
    ],
    "bsc": [
        {
            "pair": "BNB/USDT",
            "token_address": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB
            "is_native": True,
        },
        {
            "pair": "CAKE/USDT",
            "token_address": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
            "is_native": False,
        },
    ],
    "solana": [
        {
            "pair": "SOL/USDT",
            "token_address": "So11111111111111111111111111111111111111112",
            "is_native": True,
        },
        {
            "pair": "JUP/USDT",
            "token_address": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
            "is_native": False,
        },
        {
            "pair": "WIF/USDT",
            "token_address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            "is_native": False,
        },
    ],
}


class _BaseArbFn(Strategy):
    """套利策略基类"""

    chain: str = "unknown"

    def __init__(self, client, config: dict):
        super().__init__(client, config)
        self._arb_cfg = self._load_arb_config()
        self.engine = ArbitrageEngine(self._arb_cfg)
        self.feed = PriceFeedAggregator(config)
        self.executor = ArbitrageExecutor(config, chain_client=client)

        # 统计
        self._stats = {
            "scans": 0,
            "opportunities": 0,
            "executed": 0,
            "success": 0,
            "failed": 0,
            "total_profit": Decimal(0),
        }

    def _load_arb_config(self) -> ArbConfig:
        """从 config.yaml 加载套利配置"""
        arb = self.cfg if hasattr(self, 'cfg') else self.config
        arb_section = arb.get("strategies", {}).get("arbitrage", {})
        return ArbConfig(
            min_spread_pct=Decimal(str(arb_section.get("min_spread_pct", 0.3))),
            min_profit_usd=Decimal(str(arb_section.get("min_profit_usd", 2.0))),
            max_trade_usd=Decimal(str(arb_section.get("max_trade_usd", 500))),
            min_trade_usd=Decimal(str(arb_section.get("min_trade_usd", 50))),
            cex_fee_rate=Decimal(str(arb_section.get("cex_fee_rate", 0.001))),
            dex_slippage_pct=Decimal(str(arb_section.get("dex_slippage_pct", 0.3))),
            max_gas_gwei=Decimal(str(arb_section.get("max_gas_gwei", 50))),
            execution_timeout=arb_section.get("execution_timeout", 30),
            max_concurrent=arb_section.get("max_concurrent", 3),
            cooldown_seconds=arb_section.get("cooldown_seconds", 10),
        )

    async def run(self, dry_run: bool = True) -> None:
        """套利主循环"""
        await self.client.connect()
        self.feed.register_dex(self.chain, self.client)
        self.log(f"套利机器人启动 | chain={self.chain} | dry_run={dry_run}", "INFO")
        self.log(f"配置: min_spread={self._arb_cfg.min_spread_pct}% | "
                 f"max_trade=${self._arb_cfg.max_trade_usd} | "
                 f"min_profit=${self._arb_cfg.min_profit_usd}", "INFO")

        pairs = ARB_PAIRS.get(self.chain, [])
        self.log(f"监控 {len(pairs)} 个交易对", "INFO")

        try:
            await self._scan_loop(pairs, dry_run)
        except asyncio.CancelledError:
            self.log("套利机器人停止", "WARNING")
            raise
        except Exception as e:
            logger.exception(f"[{self.name}] crashed")
            self.log(f"崩溃: {e}", "ERROR")
            raise
        finally:
            await self.feed.close()
            await self.executor.close()
            await self.client.close()

    async def _scan_loop(self, pairs: list[dict], dry_run: bool) -> None:
        """持续扫描价差"""
        scan_interval = self.config.get("strategies", {}).get(
            "arbitrage", {}).get("scan_interval", 2.0)

        while True:
            self._stats["scans"] += 1

            for pair_info in pairs:
                try:
                    opp = await self._check_pair(pair_info)
                    if opp and opp.is_profitable:
                        self._stats["opportunities"] += 1
                        await self._handle_opportunity(opp, dry_run)
                except Exception as e:
                    logger.debug(f"[{self.name}] scan error for {pair_info['pair']}: {e}")

            # 定期打印统计
            if self._stats["scans"] % 30 == 0:
                self.log(
                    f"📊 扫描 {self._stats['scans']} 次 | "
                    f"发现 {self._stats['opportunities']} 个机会 | "
                    f"执行 {self._stats['executed']} | "
                    f"成功 {self._stats['success']} | "
                    f"利润 ${self._stats['total_profit']:.2f}",
                    "INFO"
                )

            await asyncio.sleep(scan_interval)

    async def _check_pair(self, pair_info: dict) -> ArbOpportunity | None:
        """检查单个交易对的套利机会"""
        pair = pair_info["pair"]
        token_address = pair_info["token_address"]

        # 并行获取 CEX + DEX 报价
        cex_task = self.feed.get_cex_quotes(pair)
        dex_task = self.feed.get_dex_quote(self.chain, token_address)

        cex_quotes, dex_quote = await asyncio.gather(cex_task, dex_task)

        if not cex_quotes or not dex_quote:
            return None

        # 估算 Gas
        gas_est = await self._estimate_gas()

        # 引擎评估
        opp = self.engine.evaluate(cex_quotes, dex_quote, gas_est)
        if opp:
            opp.token_address = token_address

        return opp

    async def _estimate_gas(self) -> GasEstimate:
        """估算当前链的 Gas 成本"""
        gas_est = GasEstimate(chain=self.chain)

        if self.chain == "solana":
            # Solana: 固定优先费
            gas_est.gas_price_gwei = Decimal("0.001")  # 等价
            gas_est.gas_limit = 1
            gas_est.native_price_usd = Decimal(
                str(await self.client._price_usd(
                    "So11111111111111111111111111111111111111112"
                ) or 100)
            )
            # Solana gas 约 $0.01-0.05
            return gas_est

        # EVM chains
        try:
            gas_price = await self.client._aw3.eth.gas_price
            gas_est.gas_price_gwei = Decimal(gas_price) / Decimal(10 ** 9)
            gas_est.gas_limit = 300_000  # swap 约 200k-400k
            native_px = await self.client._native_price_usd()
            gas_est.native_price_usd = Decimal(str(native_px))
        except Exception as e:
            logger.debug(f"gas estimate error: {e}")
            gas_est.gas_price_gwei = Decimal("30")
            gas_est.native_price_usd = Decimal("3000" if self.chain == "ethereum" else "600")

        return gas_est

    async def _handle_opportunity(self, opp: ArbOpportunity, dry_run: bool) -> None:
        """处理发现的套利机会"""
        self.log(
            f"🎯 套利机会 | {opp.pair} | {opp.direction} | "
            f"spread={opp.spread_pct:.3f}% | "
            f"est_profit=${opp.net_profit_usd:.2f} | "
            f"confidence={opp.confidence:.2f}",
            "INFO"
        )

        self.signal(
            opp.pair.split("/")[0],
            "ARB",
            float(opp.amount_usd),
            f"{opp.direction} spread={opp.spread_pct:.2f}%"
        )

        # 执行
        self.engine.mark_executed(opp.pair)
        self._stats["executed"] += 1

        try:
            result = await self.executor.execute(opp, dry_run=dry_run)

            if result.success:
                self._stats["success"] += 1
                self._stats["total_profit"] += result.profit_usd
                self.log(
                    f"✅ 套利成功 | {opp.pair} | profit=${result.profit_usd:.2f} | "
                    f"time={result.execution_time_ms:.0f}ms",
                    "SUCCESS"
                )
                notify(
                    f"💰 <b>套利成功</b>\n"
                    f"交易对: {opp.pair}\n"
                    f"方向: {opp.direction}\n"
                    f"利润: ${result.profit_usd:.2f}\n"
                    f"耗时: {result.execution_time_ms:.0f}ms"
                )
                self.position(
                    opp.pair.split("/")[0],
                    float(opp.buy_price),
                    float(opp.sell_price),
                    float(opp.amount_usd),
                )
            else:
                self._stats["failed"] += 1
                self.log(f"❌ 套利失败 | {opp.pair} | {result.error}", "ERROR")
        finally:
            self.engine.mark_completed(opp.pair)


# ========== 具体链的套利策略 ==========

class EthCexDexArb(_BaseArbFn):
    """Ethereum CEX-DEX 套利"""
    name = "eth.arb_cex_dex"
    chain = "ethereum"


class BscCexDexArb(_BaseArbFn):
    """BSC CEX-DEX 套利"""
    name = "bsc.arb_cex_dex"
    chain = "bsc"


class SolCexDexArb(_BaseArbFn):
    """Solana CEX-DEX 套利"""
    name = "sol.arb_cex_dex"
    chain = "solana"

    async def _estimate_gas(self) -> GasEstimate:
        """Solana Gas 极低"""
        gas_est = GasEstimate(chain="solana")
        gas_est.gas_price_gwei = Decimal("0.0001")
        gas_est.gas_limit = 1
        try:
            sol_px = await self.client._price_usd(
                "So11111111111111111111111111111111111111112"
            )
            gas_est.native_price_usd = Decimal(str(sol_px or 150))
        except Exception:
            gas_est.native_price_usd = Decimal("150")
        return gas_est
