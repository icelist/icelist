"""商品分类逻辑：按类型 + 价格区间打标."""
from __future__ import annotations

from typing import Iterable

from .base import Product


def _match_type(text: str, type_rules: dict[str, list[str]]) -> str:
    """根据标题/类目命中关键词决定类型，找不到则归 '其他'。"""
    text = (text or "").lower()
    for type_name, keywords in type_rules.items():
        if not keywords:
            continue
        for kw in keywords:
            if kw.lower() in text:
                return type_name
    return "其他"


def _match_price_bucket(price: float | None, buckets: list[dict]) -> str:
    if price is None:
        return "未知"
    for b in buckets:
        if b["min"] <= price < b["max"]:
            return b["name"]
    return "未知"


def classify_products(
    products: Iterable[Product],
    type_rules: dict[str, list[str]],
    price_buckets: list[dict],
) -> list[Product]:
    """就地写入 bucket_type / bucket_price 并返回列表。"""
    out: list[Product] = []
    for p in products:
        text_for_type = " ".join(
            filter(None, [p.title, p.category_path, " ".join(p.features)])
        )
        p.bucket_type = _match_type(text_for_type, type_rules)
        p.bucket_price = _match_price_bucket(p.price, price_buckets)
        out.append(p)
    return out
