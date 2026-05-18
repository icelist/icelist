"""
价格源 —— CEX + DEX 双通道实时报价

支持的 CEX：
  - Binance (Spot + Futures)
  - OKX (Spot)

支持的 DEX：
  - Uniswap V2/V3 (ETH)
  - PancakeSwap V2/V3 (BSC)
  - Jupiter (Solana)

所有报价统一为 PriceQuote 结构，引擎只管比较差价。
"""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Callable

import aiohttp

from core.logger import logger


# ---------- 数据结构 ----------

@dataclass
class PriceQuote:
    """统一报价结构"""
    source: str           # "binance" / "okx" / "uniswap_v2" / "jupiter" 等
    pair: str             # "ETH/USDT", "SOL/USDC" 等
    bid: Decimal          # 买一价（你能卖到的价格）
    ask: Decimal          # 卖一价（你能买到的价格）
    mid: Decimal          # 中间价
    timestamp: float      # Unix 时间戳
    liquidity_usd: Optional[Decimal] = None  # 可用流动性估算
    extra: dict = field(default_factory=dict)

    @property
    def spread_bps(self) -> float:
        """买卖价差（基点）"""
        if self.mid == 0:
            return 0
        return float((self.ask - self.bid) / self.mid * 10000)


@dataclass
class OrderBook:
    """简易订单簿"""
    source: str
    pair: str
    bids: list[tuple[Decimal, Decimal]]  # [(price, qty), ...]
    asks: list[tuple[Decimal, Decimal]]
    timestamp: float


# ---------- CEX 价格源 ----------

class BinanceFeed:
    """
    Binance Spot 价格源
    - REST: /api/v3/ticker/bookTicker （最佳买卖价）
    - REST: /api/v3/depth （订单簿）
    - WebSocket: 后续可接 stream
    """
    BASE_URL = "https://api.binance.com"

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self._http: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self._http is None or self._http.closed:
            headers = {}
            if self.api_key:
                headers["X-MBX-APIKEY"] = self.api_key
            self._http = aiohttp.ClientSession(headers=headers)

    async def close(self):
        if self._http and not self._http.closed:
            await self._http.close()

    async def get_quote(self, symbol: str) -> Optional[PriceQuote]:
        """
        获取 Binance 最佳买卖价
        symbol: Binance 格式，如 "ETHUSDT", "SOLUSDT"
        """
        await self._ensure_session()
        try:
            url = f"{self.BASE_URL}/api/v3/ticker/bookTicker"
            async with self._http.get(url, params={"symbol": symbol}, timeout=5) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                bid = Decimal(data["bidPrice"])
                ask = Decimal(data["askPrice"])
                mid = (bid + ask) / 2
                return PriceQuote(
                    source="binance",
                    pair=symbol,
                    bid=bid,
                    ask=ask,
                    mid=mid,
                    timestamp=time.time(),
                    liquidity_usd=Decimal(data.get("bidQty", "0")) * mid,
                )
        except Exception as e:
            logger.debug(f"[Binance] quote error {symbol}: {e}")
            return None

    async def get_orderbook(self, symbol: str, limit: int = 20) -> Optional[OrderBook]:
        """获取订单簿"""
        await self._ensure_session()
        try:
            url = f"{self.BASE_URL}/api/v3/depth"
            async with self._http.get(url, params={"symbol": symbol, "limit": limit},
                                      timeout=5) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                bids = [(Decimal(p), Decimal(q)) for p, q in data["bids"]]
                asks = [(Decimal(p), Decimal(q)) for p, q in data["asks"]]
                return OrderBook(
                    source="binance", pair=symbol,
                    bids=bids, asks=asks, timestamp=time.time(),
                )
        except Exception as e:
            logger.debug(f"[Binance] orderbook error: {e}")
            return None

    async def get_price(self, symbol: str) -> Optional[Decimal]:
        """快速获取最新成交价"""
        await self._ensure_session()
        try:
            url = f"{self.BASE_URL}/api/v3/ticker/price"
            async with self._http.get(url, params={"symbol": symbol}, timeout=5) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                return Decimal(data["price"])
        except Exception:
            return None


class OKXFeed:
    """
    OKX Spot 价格源
    """
    BASE_URL = "https://www.okx.com"

    def __init__(self, api_key: str = "", passphrase: str = "", secret: str = ""):
        self.api_key = api_key
        self._http: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession()

    async def close(self):
        if self._http and not self._http.closed:
            await self._http.close()

    async def get_quote(self, inst_id: str) -> Optional[PriceQuote]:
        """
        获取 OKX 最佳买卖价
        inst_id: OKX 格式，如 "ETH-USDT", "SOL-USDT"
        """
        await self._ensure_session()
        try:
            url = f"{self.BASE_URL}/api/v5/market/ticker"
            async with self._http.get(url, params={"instId": inst_id}, timeout=5) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                tickers = data.get("data") or []
                if not tickers:
                    return None
                t = tickers[0]
                bid = Decimal(t["bidPx"]) if t.get("bidPx") else Decimal(0)
                ask = Decimal(t["askPx"]) if t.get("askPx") else Decimal(0)
                mid = (bid + ask) / 2 if (bid and ask) else Decimal(0)
                return PriceQuote(
                    source="okx",
                    pair=inst_id,
                    bid=bid,
                    ask=ask,
                    mid=mid,
                    timestamp=time.time(),
                    liquidity_usd=Decimal(t.get("bidSz", "0")) * mid,
                )
        except Exception as e:
            logger.debug(f"[OKX] quote error {inst_id}: {e}")
            return None


# ---------- DEX 价格源 ----------

class UniswapFeed:
    """
    Uniswap V2/V3 链上报价
    通过 Router.getAmountsOut 获取
    """

    def __init__(self, client):
        """client: EVMClient 实例"""
        self.client = client
        self.name = client.name

    async def get_quote(self, token_address: str, amount_in_usd: float = 1000) -> Optional[PriceQuote]:
        """
        获取 DEX 上代币相对于稳定币的报价
        通过模拟 swap：USDC -> Token（ask）和 Token -> USDC（bid）
        """
        from chains.evm.client import CHAIN_META, UNISWAP_V2_ROUTER_ABI

        meta = CHAIN_META[self.name]
        try:
            router = self.client._aw3.eth.contract(
                address=self.client._aw3.to_checksum_address(meta["router_v2"]),
                abi=UNISWAP_V2_ROUTER_ABI,
            )
            wrapped = self.client._aw3.to_checksum_address(meta["wrapped"])
            token = self.client._aw3.to_checksum_address(token_address)

            # 用 1 个 native token 换算价格
            amt_in = 10 ** 18  # 1 ETH/BNB
            path_buy = [wrapped, token]

            try:
                outs = await router.functions.getAmountsOut(amt_in, path_buy).call()
                # token_per_native = outs[-1] (原始单位)
                token_info = await self.client.get_token_info(token_address)
                token_per_native = Decimal(outs[-1]) / Decimal(10 ** token_info.decimals)

                # 再拿 native 的 USD 价格
                native_usd = Decimal(str(await self.client._native_price_usd()))
                if native_usd == 0:
                    return None

                # ask = 买入代币的成本（USD/token）
                ask = native_usd / token_per_native if token_per_native else Decimal(0)
            except Exception:
                ask = Decimal(0)

            # 反向：Token -> Native (bid)
            try:
                # 用等值代币反向换
                token_info = await self.client.get_token_info(token_address)
                amt_token = 10 ** token_info.decimals  # 1 个 token
                path_sell = [token, wrapped]
                outs_sell = await router.functions.getAmountsOut(amt_token, path_sell).call()
                native_per_token = Decimal(outs_sell[-1]) / Decimal(10 ** 18)
                bid = native_per_token * native_usd
            except Exception:
                bid = Decimal(0)

            if ask == 0 and bid == 0:
                return None

            mid = (bid + ask) / 2 if (bid and ask) else (bid or ask)

            return PriceQuote(
                source=f"dex_{self.name}",
                pair=f"{token_info.symbol}/USD",
                bid=bid,
                ask=ask,
                mid=mid,
                timestamp=time.time(),
            )
        except Exception as e:
            logger.debug(f"[DEX:{self.name}] quote error: {e}")
            return None

    async def get_native_quote(self) -> Optional[PriceQuote]:
        """获取原生代币（ETH/BNB）的 DEX 价格"""
        try:
            px = await self.client._native_price_usd()
            if px <= 0:
                return None
            mid = Decimal(str(px))
            # DEX 价差通常较大
            spread = mid * Decimal("0.001")  # 估算 0.1% 价差
            return PriceQuote(
                source=f"dex_{self.name}",
                pair=f"{self.client.meta['native_symbol']}/USD",
                bid=mid - spread,
                ask=mid + spread,
                mid=mid,
                timestamp=time.time(),
            )
        except Exception:
            return None


class JupiterFeed:
    """
    Jupiter (Solana) 报价
    使用 Jupiter Price API v2 + Quote API
    """
    PRICE_API = "https://api.jup.ag/price/v2"
    QUOTE_API = "https://quote-api.jup.ag/v6/quote"

    def __init__(self, client=None):
        self.client = client
        self._http: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession()

    async def close(self):
        if self._http and not self._http.closed:
            await self._http.close()

    async def get_quote(self, mint: str) -> Optional[PriceQuote]:
        """获取 Solana 代币的 Jupiter 报价"""
        await self._ensure_session()
        try:
            async with self._http.get(
                self.PRICE_API, params={"ids": mint}, timeout=8
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                token_data = (data.get("data") or {}).get(mint)
                if not token_data:
                    return None
                px = Decimal(str(token_data.get("price", 0)))
                if px == 0:
                    return None
                # Jupiter 不直接给 bid/ask，用价格 ± 滑点估算
                spread = px * Decimal("0.002")  # 0.2% 估计
                return PriceQuote(
                    source="jupiter",
                    pair=f"{mint[:8]}/USD",
                    bid=px - spread,
                    ask=px + spread,
                    mid=px,
                    timestamp=time.time(),
                )
        except Exception as e:
            logger.debug(f"[Jupiter] quote error: {e}")
            return None

    async def get_swap_quote(self, input_mint: str, output_mint: str,
                             amount: int, slippage_bps: int = 50) -> Optional[dict]:
        """获取精确 swap 报价（含路由和输出数量）"""
        await self._ensure_session()
        try:
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": str(slippage_bps),
            }
            async with self._http.get(self.QUOTE_API, params=params, timeout=10) as r:
                if r.status != 200:
                    return None
                return await r.json()
        except Exception:
            return None


# ---------- 聚合器：统一管理多个价格源 ----------

class PriceFeedAggregator:
    """
    聚合多个价格源，提供统一的报价查询接口。
    套利引擎只需调用这个聚合器。
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        env = cfg.get("env", {})

        # CEX
        self.binance = BinanceFeed(
            api_key=env.get("BINANCE_API_KEY", ""),
            api_secret=env.get("BINANCE_API_SECRET", ""),
        )
        self.okx = OKXFeed(
            api_key=env.get("OKX_API_KEY", ""),
        )

        # DEX（按需延迟初始化）
        self._dex_feeds: dict[str, UniswapFeed] = {}
        self._jupiter: Optional[JupiterFeed] = None

    def register_dex(self, chain_name: str, client) -> None:
        """注册一个链的 DEX 报价源"""
        if chain_name == "solana":
            self._jupiter = JupiterFeed(client)
        else:
            self._dex_feeds[chain_name] = UniswapFeed(client)

    async def close(self):
        await self.binance.close()
        await self.okx.close()
        if self._jupiter:
            await self._jupiter.close()

    async def get_cex_quotes(self, pair: str) -> list[PriceQuote]:
        """
        获取所有 CEX 的报价
        pair: 通用格式 "ETH/USDT"
        """
        quotes = []

        # Binance: "ETH/USDT" -> "ETHUSDT"
        bn_symbol = pair.replace("/", "")
        q = await self.binance.get_quote(bn_symbol)
        if q:
            q.pair = pair
            quotes.append(q)

        # OKX: "ETH/USDT" -> "ETH-USDT"
        okx_inst = pair.replace("/", "-")
        q = await self.okx.get_quote(okx_inst)
        if q:
            q.pair = pair
            quotes.append(q)

        return quotes

    async def get_dex_quote(self, chain: str, token_address: str) -> Optional[PriceQuote]:
        """获取指定链的 DEX 报价"""
        if chain == "solana" and self._jupiter:
            return await self._jupiter.get_quote(token_address)
        elif chain in self._dex_feeds:
            return await self._dex_feeds[chain].get_quote(token_address)
        return None

    async def get_all_quotes(self, pair: str, chain: str = "",
                             token_address: str = "") -> list[PriceQuote]:
        """获取一个交易对在 CEX 和 DEX 上的所有报价"""
        tasks = [self.get_cex_quotes(pair)]
        if chain and token_address:
            tasks.append(self._wrap_dex(chain, token_address))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        quotes = []
        for r in results:
            if isinstance(r, list):
                quotes.extend(r)
            elif isinstance(r, PriceQuote):
                quotes.append(r)
        return quotes

    async def _wrap_dex(self, chain: str, token_address: str) -> Optional[PriceQuote]:
        return await self.get_dex_quote(chain, token_address)
