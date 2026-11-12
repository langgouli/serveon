"""Walmart 平台采集器（Mock 实现）。"""

from __future__ import annotations

import random

from src.pipeline.collectors.base import BaseCollector, ProductData


class WalmartCollector(BaseCollector):
    """Walmart 采集器（Mock）。"""

    platform = "Walmart"
    MAX_COUNT = 100

    def collect(self, industry: str, count: int) -> list[ProductData]:
        if count <= 0:
            return []
        count = min(count, self.MAX_COUNT)
        rng = random.Random(f"walmart:{industry}:{count}")
        products: list[ProductData] = []
        for i in range(count):
            pid = f"WMT{rng.randint(100000, 999999)}"
            products.append(
                self._make_product(
                    product_id=pid,
                    name=f"{industry}Walmart商品{i + 1}",
                    industry=industry,
                    price=round(rng.uniform(5.0, 180.0), 2),
                    rating=round(rng.uniform(3.5, 5.0), 1),
                    review_count=rng.randint(0, 3000),
                    rank=i + 1,
                    url=f"https://www.walmart.com/ip/{pid}",
                )
            )
        return products
