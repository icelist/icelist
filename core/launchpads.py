"""
即将打新活动扫描器
抓取各大 Launchpad 的公开 API / 公告页，返回 {name, chain, start_ts, token, website}
"""
from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Optional

import aiohttp
from .logger import logger


async def _fetch_json(url: str, timeout: int = 8) -> Optional[dict]:
    try:
        t = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=t) as s:
            async with s.get(url, headers={"User-Agent": "ChainSniper/0.1"}) as r:
                if r.status == 200:
                    return await r.json()
    except Exception as e:
        logger.debug(f"fetch {url[:60]} failed: {e}")
    return None


# ---------- Solana: Jupiter Studio ----------

async def jupiter_studio_upcoming() -> list[dict]:
    data = await _fetch_json("https://datapi.jup.ag/v1/pools/toptraded/5m")
    if not data:
        return []
    pools = data if isinstance(data, list) else (data.get("pools") or [])
    out = []
    for p in pools[:10]:
        base = p.get("baseAsset") or {}
        out.append({
            "chain": "solana",
            "source": "Jupiter Studio",
            "name": base.get("symbol") or base.get("name") or "?",
            "token": base.get("id") or p.get("id", ""),
            "status": "live",
            "start_ts": None,
            "website": f"https://jup.ag/studio/{base.get('id', '')}",
            "extra": {
                "mc_usd": base.get("mcap"),
                "volume_24h": p.get("volume24hUsd"),
            },
        })
    return out


# ---------- Solana: Pump.fun ----------

async def pumpfun_recent() -> list[dict]:
    data = await _fetch_json(
        "https://frontend-api.pump.fun/coins?offset=0&limit=20&sort=last_trade_timestamp&order=DESC&includeNsfw=false"
    )
    if not data:
        return []
    out = []
    for c in data[:20]:
        mc = c.get("usd_market_cap") or 0
        progress = min(100, mc / 69000 * 100)
        out.append({
            "chain": "solana",
            "source": "Pump.fun",
            "name": c.get("symbol") or c.get("name", "?"),
            "token": c.get("mint", ""),
            "status": f"bonding {progress:.0f}%" if progress < 100 else "graduated",
            "start_ts": c.get("created_timestamp"),
            "website": f"https://pump.fun/coin/{c.get('mint', '')}",
            "extra": {"mc_usd": mc, "progress": progress},
        })
    return out


# ---------- BSC: Binance Launchpool / HODLer ----------

async def binance_launchpool() -> list[dict]:
    data = await _fetch_json(
        "https://www.binance.com/bapi/defi/v1/public/launchpool/project?pageNumber=1&pageSize=10"
    )
    if not data:
        return []
    projects = ((data.get("data") or {}).get("projectList")) or []
    out = []
    for p in projects[:8]:
        status_map = {1: "upcoming", 2: "live", 3: "ended"}
        out.append({
            "chain": "bsc",
            "source": "Binance Launchpool",
            "name": p.get("name") or p.get("asset") or "?",
            "token": p.get("asset", ""),
            "status": status_map.get(p.get("status"), str(p.get("status"))),
            "start_ts": p.get("stakeStartTime"),
            "website": f"https://www.binance.com/en/launchpool/{p.get('id', '')}",
            "extra": {"apr": p.get("apr"), "total_rewards": p.get("totalRewards")},
        })
    return out


async def binance_hodler() -> list[dict]:
    data = await _fetch_json(
        "https://www.binance.com/bapi/defi/v1/public/hodler/project?pageNumber=1&pageSize=10"
    )
    if not data:
        return []
    projects = ((data.get("data") or {}).get("projectList")) or []
    out = []
    for p in projects[:8]:
        status_map = {1: "upcoming", 2: "live", 3: "ended"}
        out.append({
            "chain": "bsc",
            "source": "Binance HODLer",
            "name": p.get("name") or "?",
            "token": p.get("asset", ""),
            "status": status_map.get(p.get("status"), str(p.get("status"))),
            "start_ts": p.get("subscribeStartTime") or p.get("startTime"),
            "website": "https://www.binance.com/en/hodler-airdrops",
            "extra": {},
        })
    return out


# ---------- ETH: CoinList ----------

async def coinlist_upcoming() -> list[dict]:
    data = await _fetch_json("https://coinlist.co/api/v1/crypto/sales/upcoming")
    if not data:
        return []
    sales = data.get("sales") or data or []
    if not isinstance(sales, list):
        return []
    out = []
    for s in sales[:8]:
        out.append({
            "chain": "ethereum",
            "source": "CoinList",
            "name": s.get("name") or s.get("symbol", "?"),
            "token": s.get("symbol", ""),
            "status": s.get("status", "upcoming"),
            "start_ts": s.get("start_at"),
            "website": s.get("url") or "https://coinlist.co",
            "extra": {"raise": s.get("target_raise")},
        })
    return out


# ---------- 多链: DEXScreener boosted tokens ----------

async def dexscreener_trending() -> list[dict]:
    data = await _fetch_json("https://api.dexscreener.com/token-boosts/top/v1")
    if not data or not isinstance(data, list):
        return []
    out = []
    chain_map = {"solana": "solana", "bsc": "bsc", "ethereum": "ethereum", "base": "base"}
    for b in data[:15]:
        ch = b.get("chainId", "")
        if ch not in chain_map:
            continue
        desc = (b.get("description") or "")[:40] or "?"
        out.append({
            "chain": ch,
            "source": "DEXScreener Boosted",
            "name": desc,
            "token": b.get("tokenAddress", ""),
            "status": "trending",
            "start_ts": None,
            "website": b.get("url") or f"https://dexscreener.com/{ch}/{b.get('tokenAddress')}",
            "extra": {"amount": b.get("amount"), "boost_total": b.get("totalAmount")},
        })
    return out


# ---------- 聚合 ----------

async def fetch_all_upcoming() -> list[dict]:
    """并发抓所有源，失败的跳过"""
    tasks = [
        jupiter_studio_upcoming(),
        pumpfun_recent(),
        binance_launchpool(),
        binance_hodler(),
        coinlist_upcoming(),
        dexscreener_trending(),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out = []
    for r in results:
        if isinstance(r, list):
            out.extend(r)
    return out


def format_ts(ts) -> str:
    if not ts:
        return "—"
    try:
        t = float(ts)
        if t > 1e12:
            t = t / 1000
        return datetime.fromtimestamp(t).strftime("%m-%d %H:%M")
    except Exception:
        return str(ts)[:16]
