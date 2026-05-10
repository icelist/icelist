"""
StrategyRunner —— 在后台线程跑 asyncio 事件循环，调度策略启停

同时把 core.SignalBus 的事件通过 Qt Signal 路由到 UI 线程
"""
from __future__ import annotations
import asyncio
import threading
from PySide6.QtCore import QObject, Signal

from chains import get_client
from functions import REGISTRY as FN_REGISTRY, get_function
from core.logger import logger
from core.base import get_bus
from core.notifier import Notifier


class StrategyRunner(QObject):
    fn_started = Signal(str)
    fn_stopped = Signal(str)
    fn_error = Signal(str, str)
    # SignalBus -> Qt 桥
    signal_emitted = Signal(str, str, str, float, str)      # fn, token, action, amount, note
    position_updated = Signal(str, str, float, float, float) # fn, token, entry, current, size
    bus_log = Signal(str, str, str)                         # fn, level, msg

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._tasks: dict[str, asyncio.Task] = {}
        self._ready = threading.Event()

        # 把 SignalBus 的回调转成 Qt Signal（自动跨线程安全）
        bus = get_bus()
        bus.on_signal(lambda fn, t, a, amt, n:
                      self.signal_emitted.emit(fn, t, a, float(amt), n))
        bus.on_position(lambda fn, t, e, c, s:
                        self.position_updated.emit(fn, t, float(e), float(c), float(s)))
        bus.on_log(lambda fn, lvl, msg: self.bus_log.emit(fn, lvl, msg))

        # 初始化 notifier
        Notifier.configure(cfg)

    def update_cfg(self, cfg: dict) -> None:
        """config 被刷新（用户在 GUI 保存 API key 后调用）"""
        self.cfg = cfg
        Notifier.get().update(cfg)

    def start_loop(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5.0)

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        try:
            self._loop.run_forever()
        finally:
            try:
                self._loop.close()
            except Exception:
                pass

    def stop_loop(self) -> None:
        if self._loop and self._loop.is_running():
            for t in list(self._tasks.values()):
                self._loop.call_soon_threadsafe(t.cancel)
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=3.0)

    # ---------- 启停单个功能 ----------

    def start_fn(self, fn_code: str, dry_run: bool = True) -> None:
        if fn_code in self._tasks and not self._tasks[fn_code].done():
            logger.warning(f"[runner] {fn_code} already running")
            return
        if fn_code not in FN_REGISTRY:
            self.fn_error.emit(fn_code, f"Unknown function {fn_code}")
            return

        fn_meta = FN_REGISTRY[fn_code]
        if self._loop is None:
            self.fn_error.emit(fn_code, "event loop not ready")
            return
        self._loop.call_soon_threadsafe(
            lambda: self._spawn(fn_code, fn_meta["chain"], dry_run)
        )

    def _spawn(self, fn_code: str, chain: str, dry_run: bool) -> None:
        async def run():
            try:
                client = get_client(chain, self.cfg)
                fn_inst = get_function(fn_code, client, self.cfg)
                self.fn_started.emit(fn_code)
                await fn_inst.run(dry_run=dry_run)
            except asyncio.CancelledError:
                logger.info(f"[runner] {fn_code} cancelled")
                raise
            except Exception as e:
                logger.exception(f"[runner] {fn_code} crashed: {e}")
                self.fn_error.emit(fn_code, str(e))
            finally:
                self.fn_stopped.emit(fn_code)
                self._tasks.pop(fn_code, None)

        self._tasks[fn_code] = self._loop.create_task(run())

    def stop_fn(self, fn_code: str) -> None:
        task = self._tasks.get(fn_code)
        if task and not task.done() and self._loop:
            self._loop.call_soon_threadsafe(task.cancel)

    def running_set(self) -> set[str]:
        return {c for c, t in self._tasks.items() if not t.done()}
