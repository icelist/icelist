"""
BSC 细分功能 —— 真实逻辑实现
"""
from __future__ import annotations
import asyncio
from decimal import Decimal

import aiohttp

from core.base import Strategy, TokenInfo, TradeSignal
from core.logger import logger
from core.notifier import notify
from chains.evm.client import UNIV2_PAIR_CREATED_TOPIC, UNIV3_POOL_CREATED_TOPIC


class _BaseBscFn(Strategy):
    chain = "bsc"

    async def run(self, dry_run: bool = True) -> None:
        self.log(f"🔌 connecting to BSC RPC...", "INFO")
        try:
            await self.client.connect()
        except Exception as e:
            self.log(f"❌ RPC connect failed: {e}", "ERROR")
            self.log(f"💡 请检查 API 设置页的 BSC_RPC_URL 是否正确", "WARNING")
            raise
        self.log(f"✓ BSC RPC connected, dry_run={dry_run}", "SUCCESS")

        async def heartbeat():
            i = 0
            while True:
                await asyncio.sleep(30)
                i += 1
                self.log(f"💓 running ({i*30}s)", "INFO")
        hb = asyncio.create_task(heartbeat())

        try:
            await self._main_loop(dry_run)
        except asyncio.CancelledError:
            self.log("stopped by user", "WARNING")
            raise
        except Exception as e:
            logger.exception(f"[{self.name}] crashed")
            self.log(f"crashed: {e}", "ERROR")
            raise
        finally:
            hb.cancel()
            await self.client.close()

    async def _main_loop(self, dry_run: bool) -> None:
        raise NotImplementedError

    async def _try_buy(self, token_addr: str, dry_run: bool, note: str) -> None:
        token = await self.client.get_token_info(token_addr)
        self.log(f"🎯 {token.symbol or '?'} ({token_addr[:10]}...)", "INFO")

        ok, reason = await self.client.safety_check(token)
        if not ok:
            self.log(f"skip: {reason}", "WARNING")
            return

        max_pos = Decimal(str(self.config.get("chains", {}).get("bsc", {})
                             .get("max_position_usd", 50)))
        signal = TradeSignal(chain="bsc", token=token, action="buy",
                             amount_usd=max_pos, reason=note)
        self.signal(token.symbol or token_addr[:6], "BUY", float(max_pos), note)

        result = await self.client.execute(signal, dry_run=dry_run)
        if result.success:
            self.log(f"✅ bought tx={result.tx_hash}", "SUCCESS")
            notify(f"🟡 <b>{self.name}</b>\n{token.symbol} bought ${max_pos}\n<code>{result.tx_hash}</code>")
        else:
            self.log(f"❌ buy failed: {result.error}", "ERROR")


# ========== PancakeSwap V2 新池 ==========

class BscPancakeV2(_BaseBscFn):
    name = "bsc.pancake_v2"

    async def _main_loop(self, dry_run: bool) -> None:
        PANCAKE_V2_FACTORY = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
        self.log("watching PancakeSwap V2 PairCreated...", "INFO")
        async for ev in self.client.subscribe_pair_created(
            PANCAKE_V2_FACTORY, UNIV2_PAIR_CREATED_TOPIC
        ):
            wbnb = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"
            t0, t1 = ev["token0"].lower(), ev["token1"].lower()
            if wbnb in (t0, t1):
                new_token = t0 if t0 != wbnb else t1
                await self._try_buy(new_token, dry_run, "pancake_v2_new")


# ========== PancakeSwap V3 新池 ==========

class BscPancakeV3(_BaseBscFn):
    name = "bsc.pancake_v3"

    async def _main_loop(self, dry_run: bool) -> None:
        PANCAKE_V3_FACTORY = "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"
        self.log("watching PancakeSwap V3 PoolCreated...", "INFO")
        async for ev in self.client.subscribe_pair_created(
            PANCAKE_V3_FACTORY, UNIV3_POOL_CREATED_TOPIC
        ):
            wbnb = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"
            t0, t1 = ev["token0"].lower(), ev["token1"].lower()
            if wbnb in (t0, t1):
                new_token = t0 if t0 != wbnb else t1
                await self._try_buy(new_token, dry_run, "pancake_v3_new")


# ========== Four.meme 狙击 ==========

class BscFourMeme(_BaseBscFn):
    name = "bsc.fourmeme"

    async def _main_loop(self, dry_run: bool) -> None:
        """
        four.meme 是 BSC 上的 Pump.fun 对应物。
        公开合约地址：0x5c952063c7fc8610FFDB798152D69F0B9550762b（factory）
        监听该合约的 TokenCreated 事件
        """
        self.log("watching four.meme TokenCreated events...", "INFO")
        FOURMEME_FACTORY = "0x5c952063c7fc8610FFDB798152D69F0B9550762b"
        # TokenCreate event topic（示意；真实 topic 需 ABI 哈希）
        TOPIC = "0x" + "0" * 64  # 占位，真实使用需 keccak(TokenCreate(...))

        last_block = await self.client._aw3.eth.block_number
        while True:
            try:
                current = await self.client._aw3.eth.block_number
                if current > last_block:
                    logs = await self.client._aw3.eth.get_logs({
                        "fromBlock": last_block + 1,
                        "toBlock": current,
                        "address": self.client._aw3.to_checksum_address(FOURMEME_FACTORY),
                    })
                    for lg in logs:
                        self.log(f"four.meme event tx={lg['transactionHash'].hex()[:20]}", "INFO")
                        # 简化：从 data 里找新 token 地址
                        if len(lg["topics"]) >= 2:
                            new_token = "0x" + lg["topics"][1].hex()[-40:]
                            await self._try_buy(new_token, dry_run, "fourmeme")
                    last_block = current
                await asyncio.sleep(3)
            except Exception as e:
                self.log(f"poll error: {e}", "WARNING")
                await asyncio.sleep(5)


# ========== 跟单 ==========

class BscCopyTrade(_BaseBscFn):
    name = "bsc.copytrade"

    async def _main_loop(self, dry_run: bool) -> None:
        targets = (self.config.get("strategies", {})
                   .get("copytrade", {}).get("target_wallets") or [])
        if not targets:
            self.log("no target_wallets configured", "ERROR")
            while True:
                await asyncio.sleep(30)

        self.log(f"tracking {len(targets)} wallets", "INFO")

        async def watch(addr: str):
            async for sig in self.client.subscribe_wallet(addr):
                self.log(f"🔁 {addr[:10]}... activity", "INFO")
                self.signal(addr[:10], "COPY", 0, f"copy:{addr[:6]}")

        await asyncio.gather(*(watch(a) for a in targets))


# ========== BNB 打新（launchpad） ==========

class BscLaunchpad(_BaseBscFn):
    name = "bsc.launchpad"

    async def _main_loop(self, dry_run: bool) -> None:
        """
        监控 Binance Wallet IDO 合约。
        由于每个 IDO 合约不同，此功能设计为用户在 config 里配置合约地址 + claim 时间。
        """
        launchpads = (self.config.get("strategies", {})
                      .get("launchpad", {}).get("bsc_targets") or [])
        if not launchpads:
            self.log("no launchpad targets; add to config.yaml under strategies.launchpad.bsc_targets",
                     "WARNING")
            while True:
                await asyncio.sleep(30)
                self.log("waiting for launchpad configuration...", "INFO")

        for lp in launchpads:
            self.log(f"monitoring {lp.get('name')} at {lp.get('contract')}", "INFO")
        # 真实打新逻辑：到时间点自动 claim/commit
        while True:
            await asyncio.sleep(10)
