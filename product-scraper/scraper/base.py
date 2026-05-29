"""抓取器基类与商品数据模型."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Product:
    """统一商品数据模型，所有平台字段都映射到这里."""

    platform: str                       # alibaba1688 / pinduoduo
    product_id: str                     # 平台商品 ID
    title: str                          # 标题
    url: str                            # 详情页 URL
    price: float | None = None          # 最低价（区间取最小）
    price_text: str | None = None       # 原始价格文案
    images: list[str] = field(default_factory=list)        # 图片 URL 列表
    local_images: list[str] = field(default_factory=list)  # 下载后的本地路径
    specs: dict[str, Any] = field(default_factory=dict)    # 规格 / SKU 属性
    features: list[str] = field(default_factory=list)      # 卖点 / 特点
    category_path: str | None = None    # 平台原始类目路径
    shop: str | None = None             # 店铺名
    sales: str | None = None            # 销量文案
    keyword: str | None = None          # 抓取时使用的搜索词
    bucket_type: str | None = None      # 自动分类后的类型
    bucket_price: str | None = None     # 自动分类后的价格区间

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseScraper:
    """所有平台抓取器的抽象基类。"""

    name: str = "base"

    def __init__(self, browser, config: dict):
        self.browser = browser
        self.config = config

    # ---------- 子类需要实现 ----------
    def search(self, keyword: str, max_pages: int, limit: int) -> list[Product]:
        """搜索关键词，返回商品列表（可能仅含 id/title/url，详情留给 fetch_detail）。"""
        raise NotImplementedError

    def fetch_detail(self, product: Product) -> Product:
        """补全商品详情：价格、图片、规格、特点等。"""
        raise NotImplementedError

    def parse_url(self, url: str) -> Product | None:
        """直接通过 URL 解析为商品对象（用于 urls 模式）。"""
        raise NotImplementedError
