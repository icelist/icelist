"""
抽象基类：所有链和策略都继承自这里，保证接口一致
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import AsyncIterator, Optional, Callable


# ---------- 通用数据结构 ----------

@dataclass
class TokenInfo:
    chain: str
    address: str
    symbol: str = "???"
    decimals: int = 9
    liquidity_usd: Optional[Decimal] = None
    holders: Optional[int] = None
    creator: Optional[str] = None
    created_at: Optional[int] = None  # unix 时间戳


@dataclass
class TradeSignal:
    """由策略产生、由链客户端执行的交易信号"""
    chain: str
    token: TokenInfo
    action: str                # "buy" | "sell"
    amount_usd: Decimal
    reason: str                # 触发原因，便于日志和通知
    extra: dict = field(default_factory=dict)


@dataclass
class TradeResult:
    success: bool
    tx_hash: Optional[str] = None
    error: Optional[str] = None
    received_amount: Optional[Decimal] = None
    entry_price: Optional[Decimal] = None


# ---------- 链客户端抽象 ----------

class ChainClient(ABC):
    """每条链必须实现这些方法，策略代码只调用这些接口"""

    name: str = "unknown"

    @abstractmethod
    async def connect(self) -> None:
        """建立 RPC / WS 连接"""

    async def close(self) -> None:
        """清理资源，子类可选覆盖"""
        pass

    async def get_balance_usd(self) -> Decimal:
        """查询钱包余额（USD 等价）"""
        return Decimal(0)

    async def get_token_info(self, token_address: str) -> TokenInfo:
        """查询代币基础信息 + 流动性"""
        return TokenInfo(chain=self.name, address=token_address)

    async def subscribe_new_pairs(self) -> AsyncIterator[TokenInfo]:
        """订阅新池子事件，异步生成器；默认实现不产出"""
        if False:
            yield

    async def subscribe_wallet(self, address: str) -> AsyncIterator[TradeSignal]:
        """订阅某个钱包的交易（用于跟单）"""
        if False:
            yield

    async def execute(self, signal: TradeSignal, dry_run: bool = True) -> TradeResult:
        """执行交易"""
        return TradeResult(success=False, error="not implemented")

    async def safety_check(self, token: TokenInfo) -> tuple[bool, str]:
        """安全检查"""
        return True, "no check configured"


# ---------- 信号总线（仪表盘数据推送） ----------

class SignalBus:
    """
    策略 -> UI 的数据总线。
    策略调用 bus.emit_* ，UI 订阅 bus.on_* 回调。
    解耦 UI 和策略，便于 CLI 和 GUI 两种入口复用。
    """
    def __init__(self) -> None:
        self._signal_cbs: list[Callable] = []
        self._position_cbs: list[Callable] = []
        self._log_cbs: list[Callable] = []
        self._stat_cbs: list[Callable] = []

    # 订阅
    def on_signal(self, cb: Callable) -> None:  self._signal_cbs.append(cb)
    def on_position(self, cb: Callable) -> None: self._position_cbs.append(cb)
    def on_log(self, cb: Callable) -> None:     self._log_cbs.append(cb)
    def on_stat(self, cb: Callable) -> None:    self._stat_cbs.append(cb)

    # 发布
    def emit_signal(self, fn_code: str, token: str, action: str,
                    amount_usd: float, note: str = "") -> None:
        for cb in self._signal_cbs:
            try: cb(fn_code, token, action, amount_usd, note)
            except Exception: pass

    def emit_position(self, fn_code: str, token: str, entry: float,
                      current: float, size_usd: float) -> None:
        for cb in self._position_cbs:
            try: cb(fn_code, token, entry, current, size_usd)
            except Exception: pass

    def emit_log(self, fn_code: str, level: str, msg: str) -> None:
        for cb in self._log_cbs:
            try: cb(fn_code, level, msg)
            except Exception: pass

    def emit_stat(self, fn_code: str, key: str, value) -> None:
        for cb in self._stat_cbs:
            try: cb(fn_code, key, value)
            except Exception: pass


# 全局单例
_BUS: Optional[SignalBus] = None

def get_bus() -> SignalBus:
    global _BUS
    if _BUS is None:
        _BUS = SignalBus()
    return _BUS


# ---------- 策略抽象 ----------

class Strategy(ABC):
    """策略基类，输入是链客户端，输出是交易信号"""

    name: str = "unknown"

    def __init__(self, client: ChainClient, config: dict):
        self.client = client
        self.config = config
        self.bus = get_bus()

    @abstractmethod
    async def run(self, dry_run: bool = True) -> None:
        """策略主循环"""

    # 便捷推送
    def log(self, msg: str, level: str = "INFO") -> None:
        self.bus.emit_log(self.name, level, msg)

    def signal(self, token: str, action: str, amount_usd: float, note: str = "") -> None:
        self.bus.emit_signal(self.name, token, action, amount_usd, note)

    def position(self, token: str, entry: float, current: float, size_usd: float) -> None:
        self.bus.emit_position(self.name, token, entry, current, size_usd)
