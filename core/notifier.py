"""
通知：Telegram / Discord

所有方法都用 asyncio.create_task 做 fire-and-forget，不阻塞策略。
"""
from __future__ import annotations
import asyncio
import aiohttp
from typing import Optional
from .logger import logger


class Notifier:
    """单例通知器"""

    _instance: Optional["Notifier"] = None

    def __init__(self, cfg: dict):
        env = cfg.get("env", {})
        self.tg_token: str = env.get("TELEGRAM_BOT_TOKEN") or ""
        self.tg_chat: str = env.get("TELEGRAM_CHAT_ID") or ""
        self.discord_url: str = env.get("DISCORD_WEBHOOK_URL") or ""

    @classmethod
    def configure(cls, cfg: dict) -> "Notifier":
        cls._instance = cls(cfg)
        return cls._instance

    @classmethod
    def get(cls) -> "Notifier":
        if cls._instance is None:
            cls._instance = cls({"env": {}})
        return cls._instance

    def update(self, cfg: dict) -> None:
        """运行时刷新配置（例如用户在 GUI 里保存了新 token）"""
        env = cfg.get("env", {})
        self.tg_token = env.get("TELEGRAM_BOT_TOKEN") or ""
        self.tg_chat = env.get("TELEGRAM_CHAT_ID") or ""
        self.discord_url = env.get("DISCORD_WEBHOOK_URL") or ""

    # ---------- 同步封装 fire-and-forget ----------

    def notify(self, msg: str) -> None:
        """非阻塞发送（在 asyncio loop 中调用）"""
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self.send(msg))
        except Exception:
            pass

    async def send(self, msg: str) -> None:
        logger.info(f"[NOTIFY] {msg}")
        tasks = []
        if self.tg_token and self.tg_chat:
            tasks.append(self._send_tg(msg))
        if self.discord_url:
            tasks.append(self._send_discord(msg))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_tg(self, msg: str) -> None:
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        payload = {
            "chat_id": self.tg_chat,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.post(url, json=payload) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.warning(f"TG non-200: {resp.status} {body[:200]}")
        except Exception as e:
            logger.error(f"TG send failed: {e}")

    async def _send_discord(self, msg: str) -> None:
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as s:
                await s.post(self.discord_url, json={"content": msg})
        except Exception as e:
            logger.error(f"Discord send failed: {e}")


def notify(msg: str) -> None:
    """便捷全局函数"""
    Notifier.get().notify(msg)
