"""数据清洗：去重、字段标准化、排序。

对采集到的 ProductData 列表进行清洗，输出干净有序的数据。
清洗是确定性流程，无 LLM 参与。
"""

from __future__ import annotations

from src.pipeline.collectors.base import ProductData


class DataCleaner:
    """数据清洗器。"""

    def dedup(self, products: list[ProductData]) -> list[ProductData]:
        """按 product_id 去重，保留首次出现项。"""
        seen: set[str] = set()
        result: list[ProductData] = []
        for p in products:
            if p.product_id in seen:
                continue
            seen.add(p.product_id)
            result.append(p)
        return result

    def normalize(self, products: list[ProductData]) -> list[ProductData]:
        """字段标准化：price 保留2位、rating 保留1位、name 去首尾空格。"""
        result: list[ProductData] = []
        for p in products:
            result.append(
                p.model_copy(
                    update={
                        "price": round(p.price, 2),
                        "rating": round(p.rating, 1),
                        "name": p.name.strip(),
                    }
                )
            )
        return result

    def sort_by_rank(self, products: list[ProductData]) -> list[ProductData]:
        """按 rank 升序排序。"""
        return sorted(products, key=lambda p: p.rank)

    def clean(self, products: list[ProductData]) -> list[ProductData]:
        """完整清洗流程：标准化 -> 去重 -> 排序。"""
        return self.sort_by_rank(self.dedup(self.normalize(products)))
