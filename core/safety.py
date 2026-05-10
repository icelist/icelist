"""
代币安全检查模块
- EVM 链：GoPlus Security API（免费 + 可选付费 key）
- Solana：Rugcheck.xyz 公开 API（免费）

返回 (safe: bool, reason: str, details: dict)
"""
from __future__ import annotations
import aiohttp
from typing import Tuple
from .logger import logger


# GoPlus chain_id 映射
GOPLUS_CHAIN_IDS = {
    "ethereum": "1",
    "bsc": "56",
    "base": "8453",
    "arbitrum": "42161",
    "polygon": "137",
}


async def check_evm(chain: str, token_address: str,
                    max_buy_tax_pct: float = 10.0,
                    require_lp_lock: bool = False,
                    api_key: str = "") -> Tuple[bool, str, dict]:
    """
    GoPlus EVM 代币安全检查
    https://docs.gopluslabs.io/reference/api-token-security
    """
    chain_id = GOPLUS_CHAIN_IDS.get(chain)
    if not chain_id:
        return True, f"chain {chain} not supported by GoPlus", {}

    url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}"
    params = {"contract_addresses": token_address.lower()}
    headers = {"Accept": "*/*"}
    if api_key:
        headers["Authorization"] = api_key

    try:
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
    except Exception as e:
        logger.warning(f"GoPlus API error for {token_address}: {e}")
        return True, f"safety check unavailable (allow by default)", {}

    result = (data.get("result") or {}).get(token_address.lower()) or {}
    if not result:
        return True, "no GoPlus data (new token)", {}

    # 解析关键字段
    fails = []
    warns = []

    # 蜜罐
    if result.get("is_honeypot") == "1":
        fails.append("honeypot detected")
    # 买卖税
    try:
        buy_tax = float(result.get("buy_tax") or 0) * 100
        sell_tax = float(result.get("sell_tax") or 0) * 100
        if buy_tax > max_buy_tax_pct:
            fails.append(f"buy tax too high ({buy_tax:.1f}%)")
        if sell_tax > max_buy_tax_pct:
            fails.append(f"sell tax too high ({sell_tax:.1f}%)")
    except (TypeError, ValueError):
        pass
    # 代理 / mintable
    if result.get("is_proxy") == "1":
        warns.append("is proxy contract")
    if result.get("is_mintable") == "1":
        warns.append("is mintable")
    if result.get("owner_change_balance") == "1":
        fails.append("owner can change balance")
    if result.get("hidden_owner") == "1":
        fails.append("hidden owner")
    if result.get("selfdestruct") == "1":
        fails.append("selfdestruct function")
    # 不能卖出
    if result.get("cannot_sell_all") == "1":
        fails.append("cannot sell all")
    # LP 锁定
    if require_lp_lock:
        lp_holders = result.get("lp_holders") or []
        locked_pct = 0.0
        for h in lp_holders:
            try:
                if h.get("is_locked") == 1 or h.get("tag", "").lower().find("lock") != -1:
                    locked_pct += float(h.get("percent") or 0) * 100
            except (TypeError, ValueError):
                pass
        if locked_pct < 50.0:
            fails.append(f"LP not locked ({locked_pct:.0f}%)")

    details = {
        "buy_tax": result.get("buy_tax"),
        "sell_tax": result.get("sell_tax"),
        "is_honeypot": result.get("is_honeypot"),
        "holder_count": result.get("holder_count"),
        "total_supply": result.get("total_supply"),
        "warnings": warns,
    }

    if fails:
        return False, "; ".join(fails), details
    return True, "passed all checks" + (f" ({len(warns)} warns)" if warns else ""), details


async def check_solana(mint: str) -> Tuple[bool, str, dict]:
    """
    Rugcheck.xyz 公开 API
    https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary
    """
    url = f"https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary"
    try:
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(url) as resp:
                if resp.status != 200:
                    return True, f"rugcheck unavailable ({resp.status})", {}
                data = await resp.json()
    except Exception as e:
        logger.warning(f"Rugcheck error for {mint}: {e}")
        return True, "rugcheck unavailable", {}

    score = data.get("score", 0)
    risks = data.get("risks") or []

    fails = []
    for r in risks:
        if r.get("level") in ("danger", "critical"):
            fails.append(r.get("name") or "unknown risk")

    details = {"score": score, "risks": [r.get("name") for r in risks]}

    # rugcheck score: 越低越安全（< 1000 一般 OK，> 5000 高风险）
    if score > 5000:
        return False, f"rugcheck score too high ({score})", details
    if fails:
        return False, "; ".join(fails[:3]), details
    return True, f"rugcheck passed (score={score})", details


async def check_token(chain: str, token_address: str, cfg: dict) -> Tuple[bool, str, dict]:
    """统一入口：按链路由到对应 API"""
    env = cfg.get("env", {})
    strat_cfg = cfg.get("strategies", {}).get("sniper", {})
    max_tax = strat_cfg.get("max_buy_tax_pct", 10)
    require_lock = strat_cfg.get("require_lp_lock", False)

    if chain == "solana":
        return await check_solana(token_address)
    if chain in GOPLUS_CHAIN_IDS:
        return await check_evm(chain, token_address, max_tax, require_lock,
                               env.get("GOPLUS_KEY") or "")
    return True, "no safety API for this chain", {}
