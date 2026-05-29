"""1688 / 拼多多 商品批量抓取与分类工具."""

from .base import BaseScraper, Product
from .classifier import classify_products
from .storage import Storage

__all__ = ["BaseScraper", "Product", "classify_products", "Storage"]
