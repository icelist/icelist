"""
统一视觉主题 —— 颜色、符号、链图标
"""
from rich.theme import Theme


# 链配色（品牌色）
CHAIN_COLORS = {
    "solana":   "bright_magenta",
    "bsc":      "yellow",
    "ethereum": "bright_cyan",
}

CHAIN_ICONS = {
    "solana":   "◎",   # SOL 符号
    "bsc":      "⬢",   # 六边形
    "ethereum": "◆",   # 以太坊菱形
}

CHAIN_DISPLAY = {
    "solana":   "Solana",
    "bsc":      "BNB Chain",
    "ethereum": "Ethereum",
}

# 功能图标
FN_ICONS = {
    "sniper":    "🎯",
    "copytrade": "👥",
    "launchpad": "🚀",
    "meme":      "🔥",
}

# 通用 theme
APP_THEME = Theme({
    "info":    "cyan",
    "success": "bold green",
    "warn":    "bold yellow",
    "error":   "bold red",
    "muted":   "grey50",
    "accent":  "bold bright_magenta",
    "money":   "bold green",
    "loss":    "bold red",
    "solana":   CHAIN_COLORS["solana"],
    "bsc":      CHAIN_COLORS["bsc"],
    "ethereum": CHAIN_COLORS["ethereum"],
})
