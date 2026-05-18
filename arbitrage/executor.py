"""
套利执行器 —— 双边同时执行交易

核心思想：
  - CEX 端：通过 API 下单（市价单 / 限价单）
  - DEX 端：通过链上 swap（复用项目已有的 EVMClient / SolanaClient）
  - 两笔交易尽量同时提交，减少时间差导致的价格变化

支持模式：
  1. 原子模式：先 DEX swap 确认后再 CEX 下单（更安全）
  2. 并行模式：两边同时发起（更快，但风险略高）
"""
from __future__ import annotations
import asyncio
import time
import hmac
import hashlib
from decimal import Decimal
from typing import Optional
from urllib.parse import urlencode

import aiohttp

from core.base import TokenInfo, TradeSignal, TradeResult
from core.logger import logger
from .engine import ArbOpportunity


# ---------- 执行结果 ----------

class ArbExecutionResult:
    """套利执行结果"""
    def __init__(self):
        self.success: bool = False
        self.dex_result: Optional[TradeResult] = None
        self.cex_result: Optional[dict] = None
        self.profit_usd: Decimal = Decimal(0)
        self.error: str = ""
        self.execution_time_ms: float = 0
        self.timestamp: float = time.time()

    @property
    def summary(self) -> str:
        if self.success:
            return (f"SUCCESS | profit=${self.profit_usd:.2f} | "
                    f"time={self.execution_time_ms:.0f}ms")
        return f"FAILED | {self.error}"


# ---------- CEX 交易接口 ----------

class BinanceTrader:
    """
    Binance 现货交易接口
    - 市价买/卖
    - 限价挂单
    """
    BASE_URL = "https://api.binance.com"

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self._http: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession(headers={
                "X-MBX-APIKEY": self.api_key,
            })

    async def close(self):
        if self._http and not self._http.closed:
            await self._http.close()

    def _sign(self, params: dict) -> str:
        """HMAC SHA256 签名"""
        query = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        return signature

    async def market_buy(self, symbol: str, quote_qty: Decimal) -> dict:
        """
        市价买入（按 USDT 金额）
        symbol: "ETHUSDT"
        quote_qty: 用多少 USDT 买
        """
        await self._ensure_session()
        params = {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "quoteOrderQty": str(quote_qty),
            "timestamp": int(time.time() * 1000),
        }
        params["signature"] = self._sign(params)

        try:
            async with self._http.post(
                f"{self.BASE_URL}/api/v3/order",
                params=params, timeout=10,
            ) as r:
                data = await r.json()
                if r.status != 200:
                    return {"success": False, "error": data.get("msg", str(data))}
                return {
                    "success": True,
                    "orderId": data.get("orderId"),
                    "fills": data.get("fills", []),
                    "executedQty": data.get("executedQty"),
                    "cummulativeQuoteQty": data.get("cummulativeQuoteQty"),
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def market_sell(self, symbol: str, qty: Decimal) -> dict:
        """
        市价卖出（按币数量）
        symbol: "ETHUSDT"
        qty: 卖多少个币
        """
        await self._ensure_session()
        params = {
            "symbol": symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": str(qty),
            "timestamp": int(time.time() * 1000),
        }
        params["signature"] = self._sign(params)

        try:
            async with self._http.post(
                f"{self.BASE_URL}/api/v3/order",
                params=params, timeout=10,
            ) as r:
                data = await r.json()
                if r.status != 200:
                    return {"success": False, "error": data.get("msg", str(data))}
                return {
                    "success": True,
                    "orderId": data.get("orderId"),
                    "fills": data.get("fills", []),
                    "executedQty": data.get("executedQty"),
                    "cummulativeQuoteQty": data.get("cummulativeQuoteQty"),
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_balance(self, asset: str) -> Decimal:
        """查询指定资产余额"""
        await self._ensure_session()
        params = {"timestamp": int(time.time() * 1000)}
        params["signature"] = self._sign(params)
        try:
            async with self._http.get(
                f"{self.BASE_URL}/api/v3/account",
                params=params, timeout=10,
            ) as r:
                if r.status != 200:
                    return Decimal(0)
                data = await r.json()
                for b in data.get("balances", []):
                    if b["asset"] == asset:
                        return Decimal(b["free"])
                return Decimal(0)
        except Exception:
            return Decimal(0)


class OKXTrader:
    """OKX 现货交易接口（简化版）"""
    BASE_URL = "https://www.okx.com"

    def __init__(self, api_key: str, secret: str, passphrase: str):
        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase
        self._http: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession()

    async def close(self):
        if self._http and not self._http.closed:
            await self._http.close()

    async def market_buy(self, inst_id: str, sz: str) -> dict:
        """OKX 市价买入"""
        # 简化实现，真实需要签名
        return {"success": False, "error": "OKX trader not fully implemented"}

    async def market_sell(self, inst_id: str, sz: str) -> dict:
        """OKX 市价卖出"""
        return {"success": False, "error": "OKX trader not fully implemented"}


# ---------- 套利执行器 ----------

class ArbitrageExecutor:
    """
    执行套利交易

    支持两种执行模式：
    1. ATOMIC（原子）：先完成风险较低的一端，再执行另一端
    2. PARALLEL（并行）：两端同时提交
    """

    def __init__(self, cfg: dict, chain_client=None):
        self.cfg = cfg
        self.chain_client = chain_client
        env = cfg.get("env", {})

        # CEX 交易器
        self.binance = BinanceTrader(
            api_key=env.get("BINANCE_API_KEY", ""),
            api_secret=env.get("BINANCE_API_SECRET", ""),
        )
        self.okx = OKXTrader(
            api_key=env.get("OKX_API_KEY", ""),
            secret=env.get("OKX_API_SECRET", ""),
            passphrase=env.get("OKX_PASSPHRASE", ""),
        )

        arb_cfg = cfg.get("strategies", {}).get("arbitrage", {})
        self.mode = arb_cfg.get("execution_mode", "atomic")  # "atomic" / "parallel"

    async def close(self):
        await self.binance.close()
        await self.okx.close()

    async def execute(self, opp: ArbOpportunity, dry_run: bool = True) -> ArbExecutionResult:
        """
        执行套利

        Args:
            opp: 套利机会
            dry_run: True=模拟，False=真实执行
        """
        result = ArbExecutionResult()
        start = time.time()

        if dry_run:
            result.success = True
            result.profit_usd = opp.net_profit_usd
            result.execution_time_ms = (time.time() - start) * 1000
            logger.info(f"[ARB][DRY] {opp.direction} | {opp.pair} | "
                       f"spread={opp.spread_pct:.3f}% | "
                       f"est_profit=${opp.net_profit_usd:.2f}")
            return result

        try:
            if self.mode == "parallel":
                result = await self._execute_parallel(opp)
            else:
                result = await self._execute_atomic(opp)
        except Exception as e:
            result.success = False
            result.error = str(e)
            logger.exception(f"[ARB] execution error: {e}")

        result.execution_time_ms = (time.time() - start) * 1000
        return result

    async def _execute_atomic(self, opp: ArbOpportunity) -> ArbExecutionResult:
        """
        原子模式：
        - DEX_BUY_CEX_SELL: 先 DEX 买入确认 → 再 CEX 卖出
        - CEX_BUY_DEX_SELL: 先 CEX 买入确认 → 再 DEX 卖出
        """
        result = ArbExecutionResult()

        if opp.direction == "DEX_BUY_CEX_SELL":
            # Step 1: DEX 买入
            dex_result = await self._dex_swap(opp, "buy")
            if not dex_result.success:
                result.error = f"DEX buy failed: {dex_result.error}"
                return result
            result.dex_result = dex_result

            # Step 2: CEX 卖出
            cex_result = await self._cex_trade(opp, "sell")
            if not cex_result.get("success"):
                result.error = f"CEX sell failed: {cex_result.get('error')}"
                # 注意：DEX 已买入但 CEX 卖出失败，需要手动处理
                logger.error(f"[ARB] PARTIAL FILL! DEX bought but CEX sell failed: {result.error}")
                return result
            result.cex_result = cex_result

        else:  # CEX_BUY_DEX_SELL
            # Step 1: CEX 买入
            cex_result = await self._cex_trade(opp, "buy")
            if not cex_result.get("success"):
                result.error = f"CEX buy failed: {cex_result.get('error')}"
                return result
            result.cex_result = cex_result

            # Step 2: DEX 卖出
            dex_result = await self._dex_swap(opp, "sell")
            if not dex_result.success:
                result.error = f"DEX sell failed: {dex_result.error}"
                logger.error(f"[ARB] PARTIAL FILL! CEX bought but DEX sell failed: {result.error}")
                return result
            result.dex_result = dex_result

        result.success = True
        result.profit_usd = opp.net_profit_usd
        return result

    async def _execute_parallel(self, opp: ArbOpportunity) -> ArbExecutionResult:
        """
        并行模式：两端同时提交
        """
        result = ArbExecutionResult()

        if opp.direction == "DEX_BUY_CEX_SELL":
            dex_task = asyncio.create_task(self._dex_swap(opp, "buy"))
            cex_task = asyncio.create_task(self._cex_trade(opp, "sell"))
        else:
            dex_task = asyncio.create_task(self._dex_swap(opp, "sell"))
            cex_task = asyncio.create_task(self._cex_trade(opp, "buy"))

        dex_result, cex_result = await asyncio.gather(dex_task, cex_task)

        result.dex_result = dex_result
        result.cex_result = cex_result

        if dex_result.success and cex_result.get("success"):
            result.success = True
            result.profit_usd = opp.net_profit_usd
        else:
            errors = []
            if not dex_result.success:
                errors.append(f"DEX: {dex_result.error}")
            if not cex_result.get("success"):
                errors.append(f"CEX: {cex_result.get('error')}")
            result.error = " | ".join(errors)

        return result

    async def _dex_swap(self, opp: ArbOpportunity, action: str) -> TradeResult:
        """通过链上客户端执行 DEX swap"""
        if not self.chain_client:
            return TradeResult(success=False, error="no chain client")

        token = TokenInfo(
            chain=opp.chain,
            address=opp.token_address,
            symbol=opp.pair.split("/")[0],
        )
        signal = TradeSignal(
            chain=opp.chain,
            token=token,
            action=action,
            amount_usd=opp.amount_usd,
            reason=f"arb_{opp.direction}",
        )
        return await self.chain_client.execute(signal, dry_run=False)

    async def _cex_trade(self, opp: ArbOpportunity, action: str) -> dict:
        """在 CEX 执行交易"""
        # 根据报价来源选择交易所
        cex_source = opp.sell_source if action == "sell" else opp.buy_source

        # 转换交易对格式
        # pair: "ETH/USDT" -> Binance: "ETHUSDT"
        bn_symbol = opp.pair.replace("/", "")

        if "binance" in cex_source:
            if action == "buy":
                return await self.binance.market_buy(bn_symbol, opp.amount_usd)
            else:
                # 卖出需要知道数量
                qty = opp.amount_usd / opp.sell_price if opp.sell_price else Decimal(0)
                return await self.binance.market_sell(bn_symbol, qty)
        elif "okx" in cex_source:
            okx_inst = opp.pair.replace("/", "-")
            if action == "buy":
                return await self.okx.market_buy(okx_inst, str(opp.amount_usd))
            else:
                qty = opp.amount_usd / opp.sell_price if opp.sell_price else Decimal(0)
                return await self.okx.market_sell(okx_inst, str(qty))
        else:
            return {"success": False, "error": f"unknown CEX: {cex_source}"}
