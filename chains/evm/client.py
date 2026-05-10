"""
通用 EVM 客户端 —— Ethereum / BSC / Base 共用
- Web3 (同步) + AsyncWeb3 (异步)
- Uniswap V2 Router swap
- Factory PairCreated / PoolCreated 事件订阅
- GoPlus 安全检查
"""
from __future__ import annotations
import asyncio
import json
from decimal import Decimal
from typing import AsyncIterator, Optional

import aiohttp

from core.base import ChainClient, TokenInfo, TradeSignal, TradeResult
from core.logger import logger
from core.safety import check_evm


# ---------- 链元数据 ----------

CHAIN_META = {
    "ethereum": {
        "chain_id": 1,
        "native_symbol": "ETH",
        "wrapped": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
        "stable": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC
        "router_v2": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",  # Uniswap V2
        "factory_v2": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
        "factory_v3": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
        "env_rpc": "ETH_RPC_URL",
        "env_ws": "ETH_WS_URL",
        "env_pk": "ETH_PRIVATE_KEY",
    },
    "bsc": {
        "chain_id": 56,
        "native_symbol": "BNB",
        "wrapped": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB
        "stable": "0x55d398326f99059fF775485246999027B3197955",  # USDT
        "router_v2": "0x10ED43C718714eb63d5aA57B78B54704E256024E",  # PancakeV2
        "factory_v2": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
        "factory_v3": "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865",
        "env_rpc": "BSC_RPC_URL",
        "env_ws": "BSC_WS_URL",
        "env_pk": "BSC_PRIVATE_KEY",
    },
    "base": {
        "chain_id": 8453,
        "native_symbol": "ETH",
        "wrapped": "0x4200000000000000000000000000000000000006",
        "stable": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC
        "router_v2": "0x4752ba5DBc23f44D87826276BF6Fd6b1C372aD24",  # BaseSwap
        "factory_v2": "0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6",
        "factory_v3": "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
        "env_rpc": "BASE_RPC_URL",
        "env_ws": "",
        "env_pk": "BASE_PRIVATE_KEY",
    },
}


# ---------- ABI 精简版 ----------

ERC20_ABI = [
    {"name": "symbol", "inputs": [], "outputs": [{"type": "string"}], "stateMutability": "view", "type": "function"},
    {"name": "decimals", "inputs": [], "outputs": [{"type": "uint8"}], "stateMutability": "view", "type": "function"},
    {"name": "balanceOf", "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"name": "approve", "inputs": [{"type": "address"}, {"type": "uint256"}], "outputs": [{"type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
    {"name": "totalSupply", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
]

UNISWAP_V2_ROUTER_ABI = [
    {"name": "swapExactETHForTokensSupportingFeeOnTransferTokens",
     "inputs": [{"type": "uint256"}, {"type": "address[]"}, {"type": "address"}, {"type": "uint256"}],
     "outputs": [], "stateMutability": "payable", "type": "function"},
    {"name": "swapExactTokensForETHSupportingFeeOnTransferTokens",
     "inputs": [{"type": "uint256"}, {"type": "uint256"}, {"type": "address[]"},
                {"type": "address"}, {"type": "uint256"}],
     "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"name": "getAmountsOut",
     "inputs": [{"type": "uint256"}, {"type": "address[]"}],
     "outputs": [{"type": "uint256[]"}], "stateMutability": "view", "type": "function"},
]

# PairCreated(indexed token0, indexed token1, pair, uint256)
UNIV2_PAIR_CREATED_TOPIC = "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9"
# PoolCreated V3
UNIV3_POOL_CREATED_TOPIC = "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118"


class EVMClient(ChainClient):
    def __init__(self, cfg: dict, chain_name: str):
        self.name = chain_name
        self.cfg = cfg
        self.meta = CHAIN_META[chain_name]
        env = cfg.get("env", {})
        self.rpc = env.get(self.meta["env_rpc"]) or ""
        self.ws = env.get(self.meta["env_ws"]) or ""
        self.pk = env.get(self.meta["env_pk"]) or ""
        self.chain_cfg = cfg.get("chains", {}).get(chain_name, {})

        self._w3 = None
        self._aw3 = None
        self._acct = None
        self._address = ""
        self._http: Optional[aiohttp.ClientSession] = None

    async def connect(self) -> None:
        from web3 import AsyncWeb3, Web3
        from web3.providers.async_rpc import AsyncHTTPProvider

        self._w3 = Web3(Web3.HTTPProvider(self.rpc))
        self._aw3 = AsyncWeb3(AsyncHTTPProvider(self.rpc))

        try:
            block = await self._aw3.eth.block_number
            logger.info(f"[{self.name.upper()}] connected, block={block}")
        except Exception as e:
            logger.warning(f"[{self.name.upper()}] connect check failed: {e}")

        if self.pk:
            try:
                from eth_account import Account
                pk = self.pk if self.pk.startswith("0x") else "0x" + self.pk
                self._acct = Account.from_key(pk)
                self._address = self._acct.address
                logger.info(f"[{self.name.upper()}] wallet: {self._address[:8]}...{self._address[-6:]}")
            except Exception as e:
                logger.error(f"[{self.name.upper()}] invalid private key: {e}")

        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession()

    async def close(self) -> None:
        if self._http and not self._http.closed:
            await self._http.close()

    # ---------- 查询 ----------

    async def get_balance_usd(self) -> Decimal:
        if not self._aw3 or not self._address:
            return Decimal(0)
        try:
            wei = await self._aw3.eth.get_balance(self._address)
            native = Decimal(wei) / Decimal(10 ** 18)
            px = await self._native_price_usd()
            return native * Decimal(str(px))
        except Exception as e:
            logger.error(f"[{self.name.upper()}] balance error: {e}")
            return Decimal(0)

    async def _native_price_usd(self) -> float:
        """通过 router getAmountsOut 问 WETH->USDC 的价格"""
        try:
            router = self._aw3.eth.contract(
                address=self._aw3.to_checksum_address(self.meta["router_v2"]),
                abi=UNISWAP_V2_ROUTER_ABI,
            )
            amt_in = 10 ** 18  # 1 ETH/BNB
            path = [
                self._aw3.to_checksum_address(self.meta["wrapped"]),
                self._aw3.to_checksum_address(self.meta["stable"]),
            ]
            outs = await router.functions.getAmountsOut(amt_in, path).call()
            # stable decimals: USDC=6 USDT=18 depending on chain
            stable_decimals = 6 if self.name in ("ethereum", "base") else 18
            return float(outs[-1]) / (10 ** stable_decimals)
        except Exception:
            return 0.0

    async def get_token_info(self, token_address: str) -> TokenInfo:
        info = TokenInfo(chain=self.name, address=token_address)
        try:
            addr = self._aw3.to_checksum_address(token_address)
            c = self._aw3.eth.contract(address=addr, abi=ERC20_ABI)
            info.symbol = await c.functions.symbol().call()
            info.decimals = int(await c.functions.decimals().call())
        except Exception as e:
            logger.debug(f"[{self.name.upper()}] token info error: {e}")
        return info

    # ---------- 交易 ----------

    async def execute(self, signal: TradeSignal, dry_run: bool = True) -> TradeResult:
        slip = self.chain_cfg.get("slippage_bps", 500)

        if dry_run:
            logger.info(f"[{self.name.upper()}][DRY] {signal.action} ${signal.amount_usd} "
                        f"{signal.token.symbol} slip={slip/100}%")
            return TradeResult(success=True, tx_hash="DRY_RUN")

        if not self._acct:
            return TradeResult(success=False, error="no wallet loaded")

        try:
            if signal.action == "buy":
                return await self._buy_exact_eth(signal, slip)
            else:
                return await self._sell_all_tokens(signal, slip)
        except Exception as e:
            logger.exception(f"[{self.name.upper()}] execute error: {e}")
            return TradeResult(success=False, error=str(e))

    async def _buy_exact_eth(self, signal: TradeSignal, slip_bps: int) -> TradeResult:
        """ETH/BNB -> Token"""
        amt_usd = float(signal.amount_usd)
        native_px = await self._native_price_usd() or 3000.0
        eth_in_wei = int((amt_usd / native_px) * (10 ** 18))

        router = self._aw3.eth.contract(
            address=self._aw3.to_checksum_address(self.meta["router_v2"]),
            abi=UNISWAP_V2_ROUTER_ABI,
        )
        path = [
            self._aw3.to_checksum_address(self.meta["wrapped"]),
            self._aw3.to_checksum_address(signal.token.address),
        ]
        # 拿报价算 amountOutMin
        try:
            outs = await router.functions.getAmountsOut(eth_in_wei, path).call()
            min_out = int(outs[-1] * (10000 - slip_bps) / 10000)
        except Exception:
            min_out = 0  # 极高滑点，慎用

        deadline = int(asyncio.get_event_loop().time()) + 300
        nonce = await self._aw3.eth.get_transaction_count(self._address)
        gas_price = await self._aw3.eth.gas_price
        boost = self.chain_cfg.get("gas_boost_pct", 20)
        gas_price = int(gas_price * (100 + boost) / 100)

        fn = router.functions.swapExactETHForTokensSupportingFeeOnTransferTokens(
            min_out, path, self._address, deadline,
        )
        tx = await fn.build_transaction({
            "from": self._address,
            "value": eth_in_wei,
            "nonce": nonce,
            "gasPrice": gas_price,
            "chainId": self.meta["chain_id"],
            "gas": 500_000,
        })
        signed = self._acct.sign_transaction(tx)
        tx_hash = await self._aw3.eth.send_raw_transaction(signed.raw_transaction)
        h = tx_hash.hex()
        logger.info(f"[{self.name.upper()}] buy tx: {h}")
        return TradeResult(success=True, tx_hash=h)

    async def _sell_all_tokens(self, signal: TradeSignal, slip_bps: int) -> TradeResult:
        token_addr = self._aw3.to_checksum_address(signal.token.address)
        token = self._aw3.eth.contract(address=token_addr, abi=ERC20_ABI)
        balance = await token.functions.balanceOf(self._address).call()
        if balance == 0:
            return TradeResult(success=False, error="zero balance")

        router_addr = self._aw3.to_checksum_address(self.meta["router_v2"])
        router = self._aw3.eth.contract(address=router_addr, abi=UNISWAP_V2_ROUTER_ABI)

        # approve
        nonce = await self._aw3.eth.get_transaction_count(self._address)
        gas_price = await self._aw3.eth.gas_price
        approve_tx = await token.functions.approve(
            router_addr, 2**256 - 1
        ).build_transaction({
            "from": self._address, "nonce": nonce,
            "gasPrice": gas_price, "chainId": self.meta["chain_id"],
            "gas": 100_000,
        })
        signed_approve = self._acct.sign_transaction(approve_tx)
        approve_hash = await self._aw3.eth.send_raw_transaction(signed_approve.raw_transaction)
        await self._aw3.eth.wait_for_transaction_receipt(approve_hash, timeout=60)

        # swap
        path = [token_addr, self._aw3.to_checksum_address(self.meta["wrapped"])]
        try:
            outs = await router.functions.getAmountsOut(balance, path).call()
            min_out = int(outs[-1] * (10000 - slip_bps) / 10000)
        except Exception:
            min_out = 0

        deadline = int(asyncio.get_event_loop().time()) + 300
        nonce = await self._aw3.eth.get_transaction_count(self._address)
        fn = router.functions.swapExactTokensForETHSupportingFeeOnTransferTokens(
            balance, min_out, path, self._address, deadline,
        )
        tx = await fn.build_transaction({
            "from": self._address, "nonce": nonce,
            "gasPrice": gas_price, "chainId": self.meta["chain_id"],
            "gas": 500_000,
        })
        signed = self._acct.sign_transaction(tx)
        tx_hash = await self._aw3.eth.send_raw_transaction(signed.raw_transaction)
        h = tx_hash.hex()
        logger.info(f"[{self.name.upper()}] sell tx: {h}")
        return TradeResult(success=True, tx_hash=h)

    # ---------- 订阅 ----------

    async def subscribe_pair_created(self, factory_address: str,
                                     topic: str = UNIV2_PAIR_CREATED_TOPIC) -> AsyncIterator[dict]:
        """
        轮询 eth_getLogs 监听新池事件。
        WebSocket 不是所有 RPC 都稳定支持；用 HTTP 轮询更稳。
        """
        latest = await self._aw3.eth.block_number
        while True:
            try:
                current = await self._aw3.eth.block_number
                if current > latest:
                    logs = await self._aw3.eth.get_logs({
                        "fromBlock": latest + 1,
                        "toBlock": current,
                        "address": self._aw3.to_checksum_address(factory_address),
                        "topics": [topic],
                    })
                    for lg in logs:
                        yield {
                            "tx": lg["transactionHash"].hex(),
                            "block": lg["blockNumber"],
                            "token0": "0x" + lg["topics"][1].hex()[-40:],
                            "token1": "0x" + lg["topics"][2].hex()[-40:],
                            "data": lg["data"].hex() if hasattr(lg["data"], "hex") else str(lg["data"]),
                        }
                    latest = current
                await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"[{self.name.upper()}] getLogs error: {e}")
                await asyncio.sleep(5)

    async def subscribe_new_pairs(self) -> AsyncIterator[TokenInfo]:
        wrapped = self.meta["wrapped"].lower()
        stable = self.meta["stable"].lower()
        async for ev in self.subscribe_pair_created(self.meta["factory_v2"]):
            t0, t1 = ev["token0"].lower(), ev["token1"].lower()
            # 过滤：有一边必须是 WETH/WBNB 或稳定币
            if wrapped in (t0, t1) or stable in (t0, t1):
                new_token = t0 if t0 not in (wrapped, stable) else t1
                info = await self.get_token_info(new_token)
                yield info

    async def subscribe_wallet(self, address: str) -> AsyncIterator[TradeSignal]:
        """轮询钱包 pending / 最新交易（简化实现）"""
        addr = self._aw3.to_checksum_address(address)
        last_block = await self._aw3.eth.block_number
        while True:
            try:
                current = await self._aw3.eth.block_number
                if current > last_block:
                    for bnum in range(last_block + 1, current + 1):
                        blk = await self._aw3.eth.get_block(bnum, full_transactions=True)
                        for tx in blk.transactions:
                            if tx["from"] == addr or tx.get("to") == addr:
                                yield TradeSignal(
                                    chain=self.name,
                                    token=TokenInfo(chain=self.name, address=tx.get("to") or ""),
                                    action="buy",
                                    amount_usd=Decimal(str(tx["value"] / 10**18)),
                                    reason=f"copy:{address[:8]}",
                                    extra={"tx": tx["hash"].hex()},
                                )
                    last_block = current
                await asyncio.sleep(3)
            except Exception as e:
                logger.warning(f"[{self.name.upper()}] wallet poll error: {e}")
                await asyncio.sleep(5)

    async def safety_check(self, token: TokenInfo) -> tuple[bool, str]:
        ok, reason, _ = await check_evm(
            self.name, token.address,
            max_buy_tax_pct=self.cfg.get("strategies", {}).get("sniper", {}).get("max_buy_tax_pct", 10),
            require_lp_lock=self.cfg.get("strategies", {}).get("sniper", {}).get("require_lp_lock", False),
            api_key=self.cfg.get("env", {}).get("GOPLUS_KEY") or "",
        )
        return ok, reason
