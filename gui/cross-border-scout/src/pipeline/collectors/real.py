"""真实采集器基类（骨架，接口预留）。

当前开发阶段用 Mock 采集器。真实采集器继承 RealCollector，
实现 _fetch_raw() 完成平台接口抓取，collect() 复用基类解析逻辑。

后续接入真实接口时，按平台新建 RealAmazonCollector 等子类即可。
"""

from __future__ import annotations

from typing import Any

from src.pipeline.collectors.base import BaseCollector, ProductData


class RealCollector(BaseCollector):
    """真实采集器基类。

    子类需：
    1. 设置 platform
    2. 实现 _fetch_raw()，返回原始数据列表（dict 列表）
    """

    # 标记：真实模式（区别于 Mock）
    use_real: bool = True

    def _fetch_raw(self, industry: str, count: int) -> list[dict[str, Any]]:
        """抓取平台原始数据。

        Args:
            industry: 行业关键词
            count: 采集数量

        Returns:
            原始数据列表，每项含 product_id/name/price/rating/
            review_count/rank/url 字段

        Raises:
            NotImplementedError: 子类未实现时
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}._fetch_raw 未实现，真实接口待接入"
        )

    def collect(self, industry: str, count: int) -> list[ProductData]:
        """采集并解析为 ProductData 列表。

        调用 _fetch_raw 获取原始数据，转换为统一结构。
        """
        if count <= 0:
            return []
        raw_list = self._fetch_raw(industry, count)
        products: list[ProductData] = []
        for item in raw_list[:count]:
            products.append(
                self._make_product(
                    product_id=item["product_id"],
                    name=item["name"],
                    industry=industry,
                    price=float(item["price"]),
                    rating=float(item["rating"]),
                    review_count=int(item["review_count"]),
                    rank=int(item["rank"]),
                    url=item["url"],
                )
            )
        return products
