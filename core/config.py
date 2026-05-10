"""
配置加载：config.yaml + .env + Vault（加密保险箱）

优先级（高到低）：
  1. Vault（GUI 中用户输入的 API Key / 私钥）
  2. .env（CLI 模式 / 开发）
  3. config.yaml 默认值
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
import yaml
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent

# 所有支持的环境变量键
ENV_KEYS = [
    "DRY_RUN",
    "SOL_RPC_URL", "SOL_WS_URL", "SOL_PRIVATE_KEY",
    "HELIUS_KEY", "JITO_URL",
    "ETH_RPC_URL", "ETH_WS_URL", "ETH_PRIVATE_KEY", "ALCHEMY_ETH_KEY",
    "BSC_RPC_URL", "BSC_WS_URL", "BSC_PRIVATE_KEY", "QUICKNODE_BSC_KEY",
    "BASE_RPC_URL", "BASE_PRIVATE_KEY",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "DISCORD_WEBHOOK_URL",
    "GOPLUS_KEY", "RUGCHECK_KEY",
]


def load_config(vault=None) -> dict:
    """
    加载配置。
    如果传入 vault（已解锁），优先使用 vault 中的值覆盖 .env。
    """
    load_dotenv(ROOT / ".env")

    with open(ROOT / "config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # 1) 从环境读默认
    env = {k: os.getenv(k, "") for k in ENV_KEYS}
    env["DRY_RUN"] = os.getenv("DRY_RUN", "true").lower() == "true"

    vault_provided_rpc = {"sol": False, "eth": False, "bsc": False}

    # 2) vault 覆盖
    if vault is not None and not vault.is_locked():
        api = vault.get_api()
        for k, v in api.items():
            if v:  # 非空才覆盖
                env[k] = v
                if k == "SOL_RPC_URL": vault_provided_rpc["sol"] = True
                if k == "ETH_RPC_URL": vault_provided_rpc["eth"] = True
                if k == "BSC_RPC_URL": vault_provided_rpc["bsc"] = True
        # 私钥
        sol_pk = vault.get_private_key("solana")
        if sol_pk: env["SOL_PRIVATE_KEY"] = sol_pk
        eth_pk = vault.get_private_key("ethereum")
        if eth_pk: env["ETH_PRIVATE_KEY"] = eth_pk
        bsc_pk = vault.get_private_key("bsc")
        if bsc_pk: env["BSC_PRIVATE_KEY"] = bsc_pk

    # 3) 用 Helius/Alchemy Key 自动组装 RPC（如果用户没显式设置 RPC URL）
    helius = env.get("HELIUS_KEY") or ""
    if helius and not vault_provided_rpc["sol"]:
        env["SOL_RPC_URL"] = f"https://mainnet.helius-rpc.com/?api-key={helius}"
        env["SOL_WS_URL"] = f"wss://mainnet.helius-rpc.com/?api-key={helius}"

    alchemy_eth = env.get("ALCHEMY_ETH_KEY") or ""
    if alchemy_eth and not vault_provided_rpc["eth"]:
        env["ETH_RPC_URL"] = f"https://eth-mainnet.g.alchemy.com/v2/{alchemy_eth}"
        env["ETH_WS_URL"] = f"wss://eth-mainnet.g.alchemy.com/v2/{alchemy_eth}"

    quicknode_bsc = env.get("QUICKNODE_BSC_KEY") or ""
    if quicknode_bsc and not vault_provided_rpc["bsc"]:
        env["BSC_RPC_URL"] = quicknode_bsc  # 整个 URL 已经在 key 里

    # 4) 默认 fallback
    if not env.get("SOL_RPC_URL"):
        env["SOL_RPC_URL"] = "https://api.mainnet-beta.solana.com"
    if not env.get("SOL_WS_URL"):
        env["SOL_WS_URL"] = "wss://api.mainnet-beta.solana.com"
    if not env.get("ETH_RPC_URL"):
        env["ETH_RPC_URL"] = "https://eth.llamarpc.com"
    if not env.get("BSC_RPC_URL"):
        env["BSC_RPC_URL"] = "https://bsc-dataseed.binance.org"
    if not env.get("JITO_URL"):
        env["JITO_URL"] = "https://mainnet.block-engine.jito.wtf"

    cfg["env"] = env
    return cfg


def reload_from_vault(cfg: dict, vault) -> dict:
    """供 GUI 在用户保存 API 设置后调用，原地更新 cfg['env']"""
    new_cfg = load_config(vault)
    cfg["env"] = new_cfg["env"]
    return cfg
