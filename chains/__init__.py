"""
链注册表：新增一条链只需在这里 import + register
"""
from typing import Type
from core.base import ChainClient
from .solana.client import SolanaClient
from .evm.client import EVMClient


# 每条链的名字 -> 实现类
REGISTRY: dict[str, Type[ChainClient]] = {
    "solana": SolanaClient,
    "ethereum": lambda cfg: EVMClient(cfg, chain_name="ethereum"),
    "base": lambda cfg: EVMClient(cfg, chain_name="base"),
    "bsc": lambda cfg: EVMClient(cfg, chain_name="bsc"),
}


def get_client(chain: str, cfg: dict) -> ChainClient:
    if chain not in REGISTRY:
        raise ValueError(f"Unsupported chain: {chain}. Available: {list(REGISTRY.keys())}")
    factory = REGISTRY[chain]
    return factory(cfg) if callable(factory) and not isinstance(factory, type) else factory(cfg)
