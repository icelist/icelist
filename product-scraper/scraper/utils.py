"""通用工具函数."""
from __future__ import annotations

import hashlib
import os
import random
import re
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_from_bytes

import requests
from loguru import logger


PRICE_RE = re.compile(r"(\d+(?:\.\d+)?)")


def encode_keyword(keyword: str, encoding: str = "utf-8") -> str:
    """把关键词按指定编码 percent-encode。
    1688 历史上用 GBK，PDD 用 UTF-8。给错编码会导致网站搜索栏显示乱码。
    """
    if not keyword:
        return ""
    try:
        return quote_from_bytes(keyword.encode(encoding))
    except (UnicodeEncodeError, LookupError):
        return quote_from_bytes(keyword.encode("utf-8"))


def parse_price(text: str | None) -> float | None:
    """从形如 '￥12.50' / '12.5-39.9 元' / '￥12.50起' 中解析最低价。"""
    if not text:
        return None
    matches = PRICE_RE.findall(text)
    if not matches:
        return None
    try:
        # 区间价取最小值
        return min(float(m) for m in matches)
    except ValueError:
        return None


def sleep_random(interval: Iterable[float]) -> None:
    lo, hi = list(interval)[:2]
    time.sleep(random.uniform(lo, hi))


def safe_filename(name: str, max_len: int = 80) -> str:
    name = re.sub(r"[\\/:*?\"<>|\r\n\t]", "_", name).strip()
    return name[:max_len] or "unnamed"


def md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def download_image(url: str, save_dir: Path, prefix: str = "") -> str | None:
    """下载图片，返回本地相对路径。失败返回 None。"""
    if not url:
        return None
    if url.startswith("//"):
        url = "https:" + url

    save_dir.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(url.split("?")[0])[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        ext = ".jpg"

    fname = f"{safe_filename(prefix)}_{md5(url)[:10]}{ext}"
    fpath = save_dir / fname
    if fpath.exists():
        return str(fpath)

    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                )
            },
        )
        resp.raise_for_status()
        fpath.write_bytes(resp.content)
        return str(fpath)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"下载图片失败 {url}: {exc}")
        return None
