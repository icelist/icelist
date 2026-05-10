"""
细分功能注册表 —— 每条链的每个功能都在这里登记
新增功能：在对应 chain 文件里写类，然后在 REGISTRY 里登记即可
"""
from typing import Type
from core.base import Strategy

from .solana_fns import (
    SolPumpfunSniper, SolPumpfunGrad, SolRaydiumSniper,
    SolMeteoraSniper, SolCopyTrade, SolJupLaunchpad,
)
from .bsc_fns import (
    BscPancakeV2, BscPancakeV3, BscFourMeme,
    BscCopyTrade, BscLaunchpad,
)
from .eth_fns import (
    EthUniswapV2, EthUniswapV3, EthVirtuals,
    EthCopyTrade, EthLaunchpad,
)


# 格式：(code, chain, display_name, description, category, cls)
# category: sniper / copytrade / launchpad / meme
ALL_FUNCTIONS = [
    # ---------- Solana ----------
    ("sol.pumpfun",      "solana", "Pump.fun 早期狙击",     "监听 Pump.fun bonding curve 新代币，早期埋伏",       "meme",      SolPumpfunSniper),
    ("sol.pumpfun_grad", "solana", "Pump.fun 毕业狙击",     "监听即将毕业（达阈值）的币，转 Raydium 瞬间买入",    "meme",      SolPumpfunGrad),
    ("sol.raydium",      "solana", "Raydium 新池狙击",      "监听 Raydium V4 / CPMM 新 AMM 池创建事件",         "sniper",    SolRaydiumSniper),
    ("sol.meteora",      "solana", "Meteora DLMM 狙击",     "监听 Meteora DLMM 新池创建",                        "sniper",    SolMeteoraSniper),
    ("sol.jup_launchpad","solana", "JUP 打新",              "Jupiter Studio / LFG Launchpad / DBC 新币抢开盘",    "launchpad", SolJupLaunchpad),
    ("sol.copytrade",    "solana", "聪明钱跟单",            "订阅目标钱包交易，按比例跟单买入/卖出",              "copytrade", SolCopyTrade),

    # ---------- BSC ----------
    ("bsc.pancake_v2",   "bsc", "PancakeSwap V2 新池",     "监听 PancakeFactoryV2.PairCreated 事件",            "sniper",    BscPancakeV2),
    ("bsc.pancake_v3",   "bsc", "PancakeSwap V3 新池",     "监听 PancakeFactoryV3.PoolCreated 事件",            "sniper",    BscPancakeV3),
    ("bsc.fourmeme",     "bsc", "Four.meme 狙击",          "监听 four.meme 合约早期代币",                        "meme",      BscFourMeme),
    ("bsc.copytrade",    "bsc", "聪明钱跟单",              "订阅目标钱包 swap，按比例跟单",                      "copytrade", BscCopyTrade),
    ("bsc.launchpad",    "bsc", "BNB 打新",                "Binance Wallet IDO / 抢开盘",                        "launchpad", BscLaunchpad),

    # ---------- Ethereum ----------
    ("eth.uniswap_v2",   "ethereum", "Uniswap V2 新池",       "监听 UniswapV2Factory.PairCreated 事件",           "sniper",    EthUniswapV2),
    ("eth.uniswap_v3",   "ethereum", "Uniswap V3 新池",       "监听 UniswapV3Factory.PoolCreated 事件",           "sniper",    EthUniswapV3),
    ("eth.virtuals",     "ethereum", "Virtuals Protocol",     "监听 Virtuals 新 AI Agent 代币",                   "meme",      EthVirtuals),
    ("eth.copytrade",    "ethereum", "聪明钱跟单",            "订阅目标钱包 swap，按比例跟单",                    "copytrade", EthCopyTrade),
    ("eth.launchpad",    "ethereum", "IDO 打新",              "Legion / Echo / CoinList 打新",                    "launchpad", EthLaunchpad),
]


REGISTRY: dict[str, dict] = {
    code: {
        "code": code,
        "chain": chain,
        "display": display,
        "desc": desc,
        "category": category,
        "cls": cls,
    }
    for (code, chain, display, desc, category, cls) in ALL_FUNCTIONS
}


def functions_for_chain(chain: str) -> list[dict]:
    return [f for f in REGISTRY.values() if f["chain"] == chain]


def get_function(code: str, client, cfg: dict) -> Strategy:
    if code not in REGISTRY:
        raise ValueError(f"Unknown function: {code}")
    cls = REGISTRY[code]["cls"]
    return cls(client, cfg)
