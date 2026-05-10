"""
Solana 细分功能 —— 真实逻辑实现

所有功能类都：
1. 订阅/轮询链上事件
2. 通过 safety_check 过滤
3. 执行 execute(signal)（dry_run 或实盘）
4. 通过 bus 推送给 UI
"""
from __future__ import annotations
import asyncio
from decimal import Decimal
from datetime import datetime

import aiohttp

from core.base import Strategy, TokenInfo, TradeSignal
from core.logger import logger
from core.notifier import notify
from chains.solana.client import (
    SolanaClient, PumpfunWatcher,
    RAYDIUM_V4_PROGRAM, RAYDIUM_CPMM_PROGRAM, METEORA_DLMM_PROGRAM,
)


class _BaseSolFn(Strategy):
    chain = "solana"

    async def run(self, dry_run: bool = True) -> None:
        await self.client.connect()
        self.log(f"started on Solana, dry_run={dry_run}", "INFO")
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

    async def _try_buy(self, mint: str, dry_run: bool, note: str) -> None:
        """公共买入流程：info → safety → execute → 推仪表盘"""
        token = await self.client.get_token_info(mint)
        self.log(f"🎯 detected {token.symbol or '?'} ({mint[:8]}...)", "INFO")

        # 安全检查
        ok, reason = await self.client.safety_check(token)
        if not ok:
            self.log(f"skip: {reason}", "WARNING")
            return

        max_pos = Decimal(str(self.config.get("chains", {}).get("solana", {})
                             .get("max_position_usd", 50)))
        signal = TradeSignal(
            chain="solana", token=token, action="buy",
            amount_usd=max_pos, reason=note,
        )
        self.signal(token.symbol or mint[:6], "BUY", float(max_pos), note)

        result = await self.client.execute(signal, dry_run=dry_run)
        if result.success:
            self.log(f"✅ bought {token.symbol} tx={result.tx_hash}", "SUCCESS")
            notify(f"🟢 <b>{self.name}</b>\n{token.symbol} bought ${max_pos}\n<code>{result.tx_hash}</code>")
        else:
            self.log(f"❌ buy failed: {result.error}", "ERROR")


# ========== Pump.fun 早期狙击 ==========

class SolPumpfunSniper(_BaseSolFn):
    name = "sol.pumpfun"

    async def _main_loop(self, dry_run: bool) -> None:
        watcher = PumpfunWatcher(self.client)
        self.log("watching Pump.fun Create events...", "INFO")
        async for event in watcher.new_tokens():
            mint = event.get("mint")
            if not mint or mint == "<pending>":
                continue
            await self._try_buy(mint, dry_run, "pumpfun_new")


# ========== Pump.fun 毕业狙击 ==========

class SolPumpfunGrad(_BaseSolFn):
    name = "sol.pumpfun_grad"

    async def _main_loop(self, dry_run: bool) -> None:
        """
        轮询 Pump.fun 公开数据 API，筛选 progress > 95% 的币。
        真实毕业瞬间需要监听 program logs 同块提交 Jito bundle，
        这里简化为轮询 + 高 progress 早埋。
        """
        seen: set[str] = set()
        url = "https://frontend-api.pump.fun/coins"
        params = {"offset": 0, "limit": 50, "sort": "last_trade_timestamp",
                  "order": "DESC", "includeNsfw": "false"}

        while True:
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, params=params, timeout=10) as r:
                        if r.status == 200:
                            coins = await r.json()
                            for c in coins:
                                mint = c.get("mint")
                                progress = (c.get("usd_market_cap", 0) or 0) / 69000 * 100
                                if mint and mint not in seen and progress > 95:
                                    seen.add(mint)
                                    self.log(f"near-grad: {c.get('symbol')} progress={progress:.1f}%", "INFO")
                                    await self._try_buy(mint, dry_run,
                                                        f"near_grad_{progress:.0f}%")
            except Exception as e:
                self.log(f"poll error: {e}", "WARNING")
            await asyncio.sleep(5)


# ========== Raydium 新池狙击 ==========

class SolRaydiumSniper(_BaseSolFn):
    name = "sol.raydium"

    async def _main_loop(self, dry_run: bool) -> None:
        self.log("watching Raydium V4 initialize events...", "INFO")
        async for ev in self.client.subscribe_program_logs(RAYDIUM_V4_PROGRAM):
            logs = ev.get("logs") or []
            if ev.get("err"):
                continue
            if any("initialize2" in l.lower() for l in logs):
                sig = ev.get("signature")
                self.log(f"new pool detected sig={sig[:20]}...", "INFO")
                # TODO: 真实项目需 parse 指令 accountKeys 拿 mint；这里先用信号示意
                # 简化版用 getTransaction 反查
                mint = await self._extract_mint(sig)
                if mint:
                    await self._try_buy(mint, dry_run, "raydium_new_pool")

    async def _extract_mint(self, sig: str) -> str:
        try:
            from solders.signature import Signature
            resp = await self.client._client.get_transaction(
                Signature.from_string(sig),
                encoding="json",
                max_supported_transaction_version=0,
            )
            if not resp.value:
                return ""
            import json
            tx_json = resp.value.to_json() if hasattr(resp.value, "to_json") else None
            if tx_json:
                d = json.loads(tx_json)
                keys = d.get("transaction", {}).get("message", {}).get("accountKeys") or []
                # Raydium V4 initialize2 的代币 mint 位置：启发式从 keys 里找非 WSOL/USDC
                from chains.solana.client import SOL_MINT, USDC_MINT
                for k in keys:
                    addr = k.get("pubkey") if isinstance(k, dict) else k
                    if addr and addr not in (SOL_MINT, USDC_MINT) and len(addr) > 30:
                        return addr
        except Exception as e:
            self.log(f"extract mint failed: {e}", "WARNING")
        return ""


# ========== Meteora DLMM 狙击 ==========

class SolMeteoraSniper(_BaseSolFn):
    name = "sol.meteora"

    async def _main_loop(self, dry_run: bool) -> None:
        self.log("watching Meteora DLMM events...", "INFO")
        async for ev in self.client.subscribe_program_logs(METEORA_DLMM_PROGRAM):
            logs = ev.get("logs") or []
            if ev.get("err"):
                continue
            if any("Initialize" in l for l in logs):
                self.log(f"Meteora event: {ev.get('signature', '')[:20]}...", "INFO")
                # Meteora DLMM 的 mint 解析较复杂，此处只发信号不下单
                self.signal("METEORA_NEW", "SIGNAL", 0, "dlmm_pool_init")


# ========== JUP 打新 ==========

class SolJupLaunchpad(_BaseSolFn):
    name = "sol.jup_launchpad"

    async def _main_loop(self, dry_run: bool) -> None:
        """
        Jupiter Studio / LFG Launchpad 新币监控
        通过 Jupiter's pools API 轮询 toptraded 或 recent launches
        """
        seen: set[str] = set()
        while True:
            try:
                async with aiohttp.ClientSession() as s:
                    # Jupiter Studio 公开接口
                    url = "https://datapi.jup.ag/v1/pools/toptraded/5m"
                    async with s.get(url, timeout=10) as r:
                        if r.status != 200:
                            await asyncio.sleep(10)
                            continue
                        data = await r.json()
                        pools = data.get("pools") or data if isinstance(data, list) else []
                        for p in (pools[:20] if isinstance(pools, list) else []):
                            mint = p.get("baseAsset", {}).get("id") or p.get("id")
                            if mint and mint not in seen:
                                seen.add(mint)
                                age_s = p.get("createdAt") or 0
                                # 只打很新的
                                if age_s:
                                    created_ts = int(datetime.fromisoformat(
                                        age_s.replace("Z", "+00:00")
                                    ).timestamp()) if isinstance(age_s, str) else age_s
                                    age_min = (datetime.now().timestamp() - created_ts) / 60
                                    if age_min < 10:
                                        await self._try_buy(mint, dry_run,
                                                            f"jup_new_{age_min:.0f}min")
            except Exception as e:
                self.log(f"jup poll error: {e}", "WARNING")
            await asyncio.sleep(6)


# ========== 聪明钱跟单 ==========

class SolCopyTrade(_BaseSolFn):
    name = "sol.copytrade"

    async def _main_loop(self, dry_run: bool) -> None:
        targets = (self.config.get("strategies", {})
                   .get("copytrade", {}).get("target_wallets") or [])
        if not targets:
            self.log("no target_wallets configured; edit config.yaml", "ERROR")
            # 保持活着，定期提示
            while True:
                await asyncio.sleep(30)
                self.log("still idle: add wallets to config.yaml", "WARNING")

        ratio = Decimal(str(self.config.get("strategies", {})
                           .get("copytrade", {}).get("copy_ratio", 0.05)))
        self.log(f"tracking {len(targets)} wallets, ratio={ratio}", "INFO")

        # 并发订阅所有目标钱包
        async def watch(addr: str):
            async for sig in self.client.subscribe_wallet(addr):
                # 此处简化：只做信号提示，真实实现需 parse 交易找出 token + 方向
                self.log(f"🔁 {addr[:8]}... activity sig={sig.extra.get('signature', '?')[:20]}", "INFO")
                self.signal(addr[:8], "COPY", 0, f"copy:{addr[:6]}")

        await asyncio.gather(*(watch(a) for a in targets))
