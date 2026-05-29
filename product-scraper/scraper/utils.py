"""通用工具函数（含图片下载、防盗链 Referer、价格解析）."""
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
    """关键词按指定编码 percent-encode。1688=GBK, PDD=UTF-8。"""
    if not keyword:
        return ""
    try:
        return quote_from_bytes(keyword.encode(encoding))
    except (UnicodeEncodeError, LookupError):
        return quote_from_bytes(keyword.encode("utf-8"))


def parse_price(text: str | None) -> float | None:
    if not text:
        return None
    matches = PRICE_RE.findall(text)
    if not matches:
        return None
    try:
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
    try:
        return hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()
    except TypeError:
        return hashlib.md5(text.encode("utf-8")).hexdigest()


def _referer_for(url: str) -> str | None:
    """alicdn / pddpic 都有防盗链；没 Referer 直接 403。"""
    if not url:
        return None
    u = url.lower()
    if any(d in u for d in ("alicdn", "aliimg", "taobaocdn", "tbcdn", "1688")):
        return "https://www.1688.com/"
    if any(d in u for d in ("pddpic", "yangkeduo", "pinduoduo")):
        return "https://mobile.yangkeduo.com/"
    return None


def download_image(url: str, save_dir: Path, prefix: str = "") -> str | None:
    """下载图片，返回本地路径。失败返回 None。"""
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
    if fpath.exists() and fpath.stat().st_size > 100:
        return str(fpath)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept": "image/webp,image/jpeg,image/png,image/*,*/*;q=0.8",
    }
    ref = _referer_for(url)
    if ref:
        headers["Referer"] = ref

    try:
        resp = requests.get(url, timeout=15, headers=headers)
        resp.raise_for_status()
        if len(resp.content) < 100:
            logger.warning(f"下载得到的字节太少疑似占位图 {url}: {len(resp.content)}B")
            return None
        fpath.write_bytes(resp.content)
        return str(fpath)
    except Exception as exc:
        logger.warning(f"下载图片失败 {url}: {exc}")
        return None
