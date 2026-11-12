"""亚马逊平台采集器（Mock 实现）。

开发阶段用 Mock 数据，接口签名与真实采集器一致，
后续接入真实接口时只需替换 collect() 内部实现。
"""

from __future__ import annotations

import random

from src.pipeline.collectors.base import BaseCollector, ProductData


class AmazonCollector(BaseCollector):
    """亚马逊采集器。

    Mock 数据用固定种子生成，保证可复现。
    """

    platform = "亚马逊"
    MAX_COUNT = 100

    def collect(self, industry: str, count: int) -> list[ProductData]:
        """采集亚马逊商品（Mock）。"""
        if count <= 0:
            return []
        # 限制最大采集量，避免误传超大 count
        count = min(count, self.MAX_COUNT)
        rng = random.Random(f"amazon:{industry}:{count}")
        products: list[ProductData] = []
        for i in range(count):
            pid = f"AMZ{rng.randint(100000, 999999)}"
            products.append(
                self._make_product(
                    product_id=pid,
                    name=f"{industry}亚马逊商品{i + 1}",
                    industry=industry,
                    price=round(rng.uniform(5.0, 200.0), 2),
                    rating=round(rng.uniform(3.5, 5.0), 1),
                    review_count=rng.randint(0, 5000),
                    rank=i + 1,
                    url=f"https://www.amazon.com/dp/{pid}",
                )
            )
        return products
