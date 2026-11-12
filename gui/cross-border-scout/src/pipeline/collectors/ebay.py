"""eBay 平台采集器（Mock 实现）。"""

from __future__ import annotations

import random

from src.pipeline.collectors.base import BaseCollector, ProductData


class eBayCollector(BaseCollector):
    """eBay 采集器（Mock）。"""

    platform = "eBay"
    MAX_COUNT = 100

    def collect(self, industry: str, count: int) -> list[ProductData]:
        if count <= 0:
            return []
        count = min(count, self.MAX_COUNT)
        rng = random.Random(f"ebay:{industry}:{count}")
        products: list[ProductData] = []
        for i in range(count):
            pid = f"EBAY{rng.randint(100000, 999999)}"
            products.append(
                self._make_product(
                    product_id=pid,
                    name=f"{industry}eBay商品{i + 1}",
                    industry=industry,
                    price=round(rng.uniform(3.0, 150.0), 2),
                    rating=round(rng.uniform(3.0, 5.0), 1),
                    review_count=rng.randint(0, 2000),
                    rank=i + 1,
                    url=f"https://www.ebay.com/itm/{pid}",
                )
            )
        return products
