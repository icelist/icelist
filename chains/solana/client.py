"""
Solana 真实客户端
- AsyncClient (solana-py) 查链上数据
- Jupiter v6 Aggregator API 报价 + swap
- websockets 订阅 Pump.fun / Raydium program logs
"""
from __future__ import annotations
import asyncio
import json
import base64
from decimal import Decimal
from typing import AsyncIterator, Optional

import aiohttp

from core.base import ChainClient, TokenInfo, TradeSignal, TradeResult
from core.logger import logger
from core.safety import check_solana


# ---- 常量 ----
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
JUPITER_API = "https://quote-api.jup.ag/v6"
JUPITER_PRICE = "https://api.jup.ag/price/v2"

PUMPFUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
RAYDIUM_V4_PROGRAM = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_CPMM_PROGRAM = "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C"
METEORA_DLMM_PROGRAM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"


class SolanaClient(ChainClient):
    name = "solana"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        env = cfg.get("env", {})
        self.rpc = env.get("SOL_RPC_URL") or "https://api.mainnet-beta.solana.com"
        self.ws_url = env.get("SOL_WS_URL") or self.rpc.replace("https://", "wss://").replace("http://", "ws://")
        self.pk = env.get("SOL_PRIVATE_KEY") or ""
        self.chain_cfg = cfg.get("chains", {}).get("solana", {})

        self._client = None
        self._keypair = None
        self._pubkey_str = ""
        self._http: Optional[aiohttp.ClientSession] = None

    async def connect(self) -> None:
        # 延迟导入：依赖未装时也不影响 GUI 启动
        from solana.rpc.async_api import AsyncClient
        self._client = AsyncClient(self.rpc)
        # 测试链接
        try:
            health = await self._client.is_connected()
            logger.info(f"[SOL] RPC {self.rpc} connected={health}")
        except Exception as e:
            logger.warning(f"[SOL] RPC check failed: {e}")

        # 加载钱包
        if self.pk:
            try:
                from solders.keypair import Keypair
                import base58
                self._keypair = Keypair.from_bytes(base58.b58decode(self.pk))
                self._pubkey_str = str(self._keypair.pubkey())
                logger.info(f"[SOL] Wallet: {self._pubkey_str[:8]}...{self._pubkey_str[-6:]}")
            except Exception as e:
                logger.error(f"[SOL] Invalid private key: {e}")

        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession()

    async def close(self) -> None:
        if self._client:
            await self._client.close()
        if self._http and not self._http.closed:
            await self._http.close()

    # ---------- 查询 ----------

    async def get_balance_usd(self) -> Decimal:
        if not self._client or not self._pubkey_str:
            return Decimal(0)
        try:
            from solders.pubkey import Pubkey
            resp = await self._client.get_balance(Pubkey.from_string(self._pubkey_str))
            sol = Decimal(resp.value) / Decimal(1_000_000_000)
            # 取 SOL 价格
            sol_usd = await self._price_usd(SOL_MINT)
            return sol * Decimal(str(sol_usd))
        except Exception as e:
            logger.error(f"[SOL] get_balance error: {e}")
            return Decimal(0)

    async def _price_usd(self, mint: str) -> float:
        if not self._http:
            self._http = aiohttp.ClientSession()
        try:
            async with self._http.get(f"{JUPITER_PRICE}?ids={mint}", timeout=8) as r:
                data = await r.json()
                px = (data.get("data") or {}).get(mint) or {}
                return float(px.get("price") or 0)
        except Exception:
            return 0.0

    async def get_token_info(self, mint: str) -> TokenInfo:
        info = TokenInfo(chain="solana", address=mint)
        # 问 Jupiter token list
        try:
            async with self._http.get(f"https://tokens.jup.ag/token/{mint}", timeout=6) as r:
                if r.status == 200:
                    data = await r.json()
                    info.symbol = data.get("symbol") or "?"
                    info.decimals = int(data.get("decimals") or 9)
        except Exception:
            pass
        return info

    # ---------- 交易 ----------

    async def execute(self, signal: TradeSignal, dry_run: bool = True) -> TradeResult:
        """通过 Jupiter v6 执行 swap（支持 buy/sell 双向）"""
        if signal.action == "buy":
            input_mint, output_mint = SOL_MINT, signal.token.address
            in_amount_usd = float(signal.amount_usd)
            sol_px = await self._price_usd(SOL_MINT) or 100.0
            in_lamports = int((in_amount_usd / sol_px) * 1_000_000_000)
        else:  # sell
            input_mint, output_mint = signal.token.address, SOL_MINT
            # 简化：按 amount_usd 反算代币数量
            token_px = await self._price_usd(signal.token.address) or 0
            if token_px <= 0:
                return TradeResult(success=False, error="cannot price token")
            in_amount_tokens = float(signal.amount_usd) / token_px
            in_lamports = int(in_amount_tokens * (10 ** signal.token.decimals))

        slippage_bps = self.chain_cfg.get("slippage_bps", 500)

        if dry_run:
            logger.info(f"[SOL][DRY] {signal.action} {signal.amount_usd} USD {signal.token.symbol}")
            return TradeResult(success=True, tx_hash="DRY_RUN")

        if not self._keypair:
            return TradeResult(success=False, error="no wallet loaded")

        # Jupiter quote
        try:
            quote = await self._jupiter_quote(input_mint, output_mint, in_lamports, slippage_bps)
            if not quote:
                return TradeResult(success=False, error="no quote")
            # Jupiter swap tx
            swap_tx_b64 = await self._jupiter_swap_tx(quote)
            if not swap_tx_b64:
                return TradeResult(success=False, error="swap tx build failed")
            # 签名 + 发送
            tx_hash = await self._sign_and_send(swap_tx_b64)
            return TradeResult(success=True, tx_hash=tx_hash,
                               received_amount=Decimal(str(quote.get("outAmount", 0))))
        except Exception as e:
            logger.exception(f"[SOL] execute error: {e}")
            return TradeResult(success=False, error=str(e))

    async def _jupiter_quote(self, input_mint: str, output_mint: str,
                             amount: int, slippage_bps: int) -> Optional[dict]:
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": str(slippage_bps),
            "onlyDirectRoutes": "false",
            "asLegacyTransaction": "false",
        }
        async with self._http.get(f"{JUPITER_API}/quote", params=params, timeout=10) as r:
            if r.status != 200:
                txt = await r.text()
                logger.warning(f"Jupiter quote failed: {r.status} {txt[:200]}")
                return None
            return await r.json()

    async def _jupiter_swap_tx(self, quote: dict) -> Optional[str]:
        payload = {
            "quoteResponse": quote,
            "userPublicKey": self._pubkey_str,
            "wrapAndUnwrapSol": True,
            "computeUnitPriceMicroLamports": self.chain_cfg.get("priority_fee_lamports", 100000),
            "dynamicComputeUnitLimit": True,
        }
        async with self._http.post(f"{JUPITER_API}/swap", json=payload, timeout=15) as r:
            if r.status != 200:
                txt = await r.text()
                logger.warning(f"Jupiter swap failed: {r.status} {txt[:200]}")
                return None
            data = await r.json()
            return data.get("swapTransaction")

    async def _sign_and_send(self, swap_tx_b64: str) -> str:
        from solders.transaction import VersionedTransaction
        from solana.rpc.types import TxOpts

        raw = base64.b64decode(swap_tx_b64)
        vtx = VersionedTransaction.from_bytes(raw)
        signed = VersionedTransaction(vtx.message, [self._keypair])

        resp = await self._client.send_raw_transaction(
            bytes(signed), opts=TxOpts(skip_preflight=True, max_retries=3)
        )
        sig = str(resp.value)
        logger.info(f"[SOL] tx sent: {sig}")
        return sig

    # ---------- 订阅 ----------

    async def subscribe_program_logs(self, program_id: str) -> AsyncIterator[dict]:
        """
        WebSocket 订阅指定 program 的日志。
        返回的 dict 包含：signature、logs (list[str])、slot
        """
        import websockets

        sub_msg = {
            "jsonrpc": "2.0", "id": 1, "method": "logsSubscribe",
            "params": [{"mentions": [program_id]}, {"commitment": "processed"}]
        }

        while True:
            try:
                async with websockets.connect(self.ws_url, ping_interval=20) as ws:
                    await ws.send(json.dumps(sub_msg))
                    await ws.recv()  # ack
                    logger.info(f"[SOL] subscribed to {program_id[:10]}...")

                    while True:
                        raw = await ws.recv()
                        try:
                            msg = json.loads(raw)
                            params = msg.get("params") or {}
                            val = (params.get("result") or {}).get("value") or {}
                            if val:
                                yield {
                                    "signature": val.get("signature"),
                                    "logs": val.get("logs") or [],
                                    "slot": (params.get("result") or {}).get("context", {}).get("slot"),
                                    "err": val.get("err"),
                                }
                        except Exception as e:
                            logger.debug(f"[SOL] parse log failed: {e}")
            except Exception as e:
                logger.warning(f"[SOL] WS disconnected: {e}, reconnecting in 3s")
                await asyncio.sleep(3)

    async def subscribe_new_pairs(self) -> AsyncIterator[TokenInfo]:
        """默认订阅 Raydium V4 新池"""
        async for ev in self.subscribe_program_logs(RAYDIUM_V4_PROGRAM):
            logs = ev.get("logs") or []
            if any("initialize2" in l.lower() for l in logs) and not ev.get("err"):
                # 从 logs 提取 mint 比较复杂，这里只给出信号
                yield TokenInfo(chain="solana", address="<pending>", symbol="?",
                                decimals=9, created_at=ev.get("slot"))

    async def subscribe_wallet(self, address: str) -> AsyncIterator[TradeSignal]:
        """订阅指定地址的日志"""
        async for ev in self.subscribe_program_logs(address):
            if ev.get("err"):
                continue
            logs = ev.get("logs") or []
            is_swap = any("swap" in l.lower() or "Instruction: Swap" in l for l in logs)
            if not is_swap:
                continue
            yield TradeSignal(
                chain="solana",
                token=TokenInfo(chain="solana", address="<from_logs>"),
                action="buy",
                amount_usd=Decimal(0),
                reason=f"copy:{address[:8]}",
                extra={"signature": ev.get("signature")},
            )

    async def safety_check(self, token: TokenInfo) -> tuple[bool, str]:
        ok, reason, _ = await check_solana(token.address)
        return ok, reason


# ---------- Pump.fun 特殊订阅 ----------

class PumpfunWatcher:
    """
    Pump.fun 新币监听：解析 Create 指令拿 mint
    Pump.fun 用 Anchor，Create 指令的 discriminator 是固定的 8 字节前缀
    """
    PROGRAM = PUMPFUN_PROGRAM

    def __init__(self, client: SolanaClient):
        self.client = client

    async def new_tokens(self) -> AsyncIterator[dict]:
        """
        yields: {mint, signature, bonding_curve, creator}
        """
        async for ev in self.client.subscribe_program_logs(self.PROGRAM):
            logs = ev.get("logs") or []
            # Pump.fun Create 指令会打印 "Program log: Instruction: Create"
            if any("Instruction: Create" in l for l in logs) and not ev.get("err"):
                # 解析 mint：最可靠的方式是获取交易详情
                sig = ev.get("signature")
                if not sig:
                    continue
                mint = await self._extract_mint_from_tx(sig)
                if mint:
                    yield {
                        "mint": mint,
                        "signature": sig,
                        "slot": ev.get("slot"),
                    }

    async def _extract_mint_from_tx(self, signature: str) -> Optional[str]:
        """通过 getTransaction 反查 mint 地址"""
        try:
            from solders.signature import Signature
            resp = await self.client._client.get_transaction(
                Signature.from_string(signature),
                encoding="json",
                max_supported_transaction_version=0,
            )
            if not resp.value:
                return None
            # 新 mint 一般是静态账户里 Pump.fun 之后第一个 writable 账户
            tx_json = resp.value.to_json() if hasattr(resp.value, "to_json") else None
            if tx_json:
                data = json.loads(tx_json)
                acct_keys = (data.get("transaction", {})
                                 .get("message", {}).get("accountKeys") or [])
                # 启发式：第二个账户一般是 mint
                for k in acct_keys[1:5]:
                    if isinstance(k, dict):
                        k = k.get("pubkey")
                    if k and k != PUMPFUN_PROGRAM and len(k) >= 32:
                        return k
        except Exception as e:
            logger.debug(f"extract mint failed: {e}")
        return None
