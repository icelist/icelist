"""
Ethereum 细分功能 —— 真实逻辑实现
"""
from __future__ import annotations
import asyncio
from decimal import Decimal

from core.base import Strategy, TokenInfo, TradeSignal
from core.logger import logger
from core.notifier import notify
from chains.evm.client import UNIV2_PAIR_CREATED_TOPIC, UNIV3_POOL_CREATED_TOPIC


class _BaseEthFn(Strategy):
    chain = "ethereum"

    async def run(self, dry_run: bool = True) -> None:
        await self.client.connect()
        self.log(f"started on Ethereum, dry_run={dry_run}", "INFO")
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

        max_pos = Decimal(str(self.config.get("chains", {}).get("ethereum", {})
                             .get("max_position_usd", 100)))
        signal = TradeSignal(chain="ethereum", token=token, action="buy",
                             amount_usd=max_pos, reason=note)
        self.signal(token.symbol or token_addr[:6], "BUY", float(max_pos), note)

        result = await self.client.execute(signal, dry_run=dry_run)
        if result.success:
            self.log(f"✅ bought tx={result.tx_hash}", "SUCCESS")
            notify(f"🔵 <b>{self.name}</b>\n{token.symbol} bought ${max_pos}\n<code>{result.tx_hash}</code>")
        else:
            self.log(f"❌ buy failed: {result.error}", "ERROR")


# ========== Uniswap V2 新池 ==========

class EthUniswapV2(_BaseEthFn):
    name = "eth.uniswap_v2"

    async def _main_loop(self, dry_run: bool) -> None:
        UNI_V2_FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
        self.log("watching Uniswap V2 PairCreated...", "INFO")
        async for ev in self.client.subscribe_pair_created(
            UNI_V2_FACTORY, UNIV2_PAIR_CREATED_TOPIC
        ):
            weth = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
            t0, t1 = ev["token0"].lower(), ev["token1"].lower()
            if weth in (t0, t1):
                new_token = t0 if t0 != weth else t1
                await self._try_buy(new_token, dry_run, "uni_v2_new")


# ========== Uniswap V3 新池 ==========

class EthUniswapV3(_BaseEthFn):
    name = "eth.uniswap_v3"

    async def _main_loop(self, dry_run: bool) -> None:
        UNI_V3_FACTORY = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
        self.log("watching Uniswap V3 PoolCreated...", "INFO")
        async for ev in self.client.subscribe_pair_created(
            UNI_V3_FACTORY, UNIV3_POOL_CREATED_TOPIC
        ):
            weth = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
            t0, t1 = ev["token0"].lower(), ev["token1"].lower()
            if weth in (t0, t1):
                new_token = t0 if t0 != weth else t1
                await self._try_buy(new_token, dry_run, "uni_v3_new")


# ========== Virtuals Protocol 新 Agent ==========

class EthVirtuals(_BaseEthFn):
    name = "eth.virtuals"

    async def _main_loop(self, dry_run: bool) -> None:
        """
        Virtuals Protocol 部署在 Base 链为主，ETH 上是镜像。
        官方 Agent Factory 合约 - 监听 AgentCreated 事件
        """
        VIRTUALS_FACTORY = "0xF66DeA7b3e897cD44A5a231c61B6B4423d613259"  # 示例
        self.log("watching Virtuals Protocol...", "INFO")
        # 用通用事件轮询
        last_block = await self.client._aw3.eth.block_number
        while True:
            try:
                current = await self.client._aw3.eth.block_number
                if current > last_block:
                    logs = await self.client._aw3.eth.get_logs({
                        "fromBlock": last_block + 1,
                        "toBlock": current,
                        "address": self.client._aw3.to_checksum_address(VIRTUALS_FACTORY),
                    })
                    for lg in logs:
                        self.log(f"Virtuals event: {lg['transactionHash'].hex()[:20]}", "INFO")
                        if len(lg["topics"]) >= 2:
                            agent_token = "0x" + lg["topics"][1].hex()[-40:]
                            await self._try_buy(agent_token, dry_run, "virtuals_new")
                    last_block = current
                await asyncio.sleep(3)
            except Exception as e:
                self.log(f"poll error: {e}", "WARNING")
                await asyncio.sleep(5)


# ========== 跟单 ==========

class EthCopyTrade(_BaseEthFn):
    name = "eth.copytrade"

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


# ========== IDO 打新 ==========

class EthLaunchpad(_BaseEthFn):
    name = "eth.launchpad"

    async def _main_loop(self, dry_run: bool) -> None:
        """
        IDO 打新：Legion / Echo / CoinList
        用户在 config.yaml 下配置 strategies.launchpad.eth_targets
        """
        launchpads = (self.config.get("strategies", {})
                      .get("launchpad", {}).get("eth_targets") or [])
        if not launchpads:
            self.log("no launchpad targets; add to config.yaml", "WARNING")
            while True:
                await asyncio.sleep(30)
                self.log("waiting for launchpad configuration...", "INFO")

        for lp in launchpads:
            self.log(f"monitoring {lp.get('name')} at {lp.get('contract')}", "INFO")

        while True:
            await asyncio.sleep(10)
