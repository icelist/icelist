"""命令行入口：批量抓取 1688 / 拼多多 商品，按"类型 + 价格"分类导出.

用法示例：
    python main.py                       # 使用 config.yaml 默认配置
    python main.py -c custom.yaml        # 指定配置文件
    python main.py -k 蓝牙耳机 充电宝     # 临时覆盖关键词
    python main.py --no-images           # 关掉图片下载
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from loguru import logger
from tqdm import tqdm

from scraper.alibaba1688 import Alibaba1688Scraper
from scraper.classifier import classify_products
from scraper.pinduoduo import PinduoduoScraper
from scraper.storage import Storage
from scraper.utils import sleep_random


SCRAPER_REGISTRY = {
    "alibaba1688": Alibaba1688Scraper,
    "pinduoduo": PinduoduoScraper,
}


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_browser(cfg: dict):
    """延迟导入 DrissionPage，避免无头环境 import 失败。"""
    from DrissionPage import ChromiumPage, ChromiumOptions

    opts = ChromiumOptions()
    opts.set_user_data_path(cfg["browser"].get("user_data_dir", ".browser_profile"))
    if cfg["browser"].get("headless"):
        opts.headless()
    # 反检测：去掉 webdriver 痕迹
    opts.set_argument("--disable-blink-features=AutomationControlled")
    opts.set_argument("--lang=zh-CN")
    return ChromiumPage(opts)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="1688 / 拼多多 商品批量抓取与分类")
    p.add_argument("-c", "--config", default="config.yaml", help="配置文件路径")
    p.add_argument("-k", "--keywords", nargs="*", help="覆盖配置中的关键词")
    p.add_argument("-u", "--urls", nargs="*", help="直接抓取的商品 URL 列表")
    p.add_argument(
        "-p",
        "--platforms",
        nargs="*",
        choices=list(SCRAPER_REGISTRY.keys()),
        help="覆盖启用的平台",
    )
    p.add_argument("--no-images", action="store_true", help="不下载图片")
    p.add_argument("--limit", type=int, help="覆盖每关键词抓取数量")
    p.add_argument("--pages", type=int, help="覆盖最大翻页数")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        logger.error(f"配置文件不存在：{cfg_path}")
        return 2
    cfg = load_config(cfg_path)

    # 命令行覆盖
    if args.keywords:
        cfg["keywords"] = args.keywords
    if args.urls:
        cfg["urls"] = args.urls
    if args.platforms:
        cfg["platforms"] = args.platforms
    if args.no_images:
        cfg["download_images"] = False
    if args.limit:
        cfg["per_keyword_limit"] = args.limit
    if args.pages:
        cfg["max_pages"] = args.pages

    logger.info(f"启用平台: {cfg['platforms']}")
    logger.info(f"关键词: {cfg.get('keywords') or '<无>'}  URL 数: {len(cfg.get('urls') or [])}")

    browser = build_browser(cfg)

    all_products = []
    try:
        for plat in cfg["platforms"]:
            scraper_cls = SCRAPER_REGISTRY.get(plat)
            if not scraper_cls:
                logger.warning(f"未知平台：{plat}")
                continue
            scraper = scraper_cls(browser, cfg)

            # 1) URL 直采
            for url in cfg.get("urls") or []:
                if plat not in url and not _url_matches(url, plat):
                    continue
                prod = scraper.parse_url(url)
                if prod:
                    all_products.append(prod)
                sleep_random(cfg["browser"]["request_interval"])

            # 2) 关键词搜索
            for kw in cfg.get("keywords") or []:
                products = scraper.search(
                    kw,
                    max_pages=cfg["max_pages"],
                    limit=cfg["per_keyword_limit"],
                )
                # 详情补全
                for p in tqdm(products, desc=f"[{plat}] 抓详情 {kw}"):
                    try:
                        scraper.fetch_detail(p)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(f"详情抓取失败 {p.url}: {exc}")
                    sleep_random(cfg["browser"]["request_interval"])
                all_products.extend(products)
    finally:
        try:
            browser.quit()
        except Exception:  # noqa: BLE001
            pass

    if not all_products:
        logger.error("没有抓到任何商品。请检查关键词、网络、或是否被风控。")
        return 1

    # 分类
    classify_products(
        all_products,
        type_rules=cfg["type_rules"],
        price_buckets=cfg["price_buckets"],
    )

    # 落地
    storage = Storage(cfg["output"])
    if cfg.get("download_images"):
        storage.download_images_for(all_products)

    paths = storage.save(all_products)
    logger.success(f"完成。共 {len(all_products)} 件商品。输出：{paths}")
    return 0


def _url_matches(url: str, platform: str) -> bool:
    """简单匹配 URL 与平台关系，避免把 1688 链接喂给 PDD。"""
    if platform == "alibaba1688":
        return "1688.com" in url
    if platform == "pinduoduo":
        return "yangkeduo.com" in url or "pinduoduo.com" in url
    return False


if __name__ == "__main__":
    sys.exit(main())
