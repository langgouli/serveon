"""Task 1.8 数据清洗测试。

覆盖：正常（去重/标准化/排序/完整流程）、边界（空/单元素/无重复）、不变性。
"""

from __future__ import annotations

from src.pipeline.cleaners.cleaner import DataCleaner
from src.pipeline.collectors.base import ProductData


def make(
    pid: str,
    rank: int = 1,
    price: float = 10.0,
    rating: float = 4.0,
    name: str = "商品",
    review_count: int = 1,
) -> ProductData:
    """构造测试用 ProductData。"""
    return ProductData(
        product_id=pid, name=name, industry="宠物用品", platform="亚马逊",
        price=price, rating=rating, review_count=review_count, rank=rank,
        url=f"https://example.com/{pid}",
    )


def test_dedup_keeps_first() -> None:
    """正常场景：重复 product_id 保留首次出现项。"""
    cleaner = DataCleaner()
    p1 = make("P1", rank=1)
    p1_dup = make("P1", rank=2, price=30.0)
    p2 = make("P2", rank=3)
    result = cleaner.dedup([p1, p1_dup, p2])
    assert len(result) == 2
    assert result[0].rank == 1


def test_dedup_empty() -> None:
    """边界场景：空列表返回空。"""
    assert DataCleaner().dedup([]) == []


def test_normalize_price_rating_name() -> None:
    """正常场景：price/rating 保留位数、name 去空格。"""
    p = make("P1", price=10.123, rating=4.567, name=" 商品 ")
    result = DataCleaner().normalize([p])[0]
    assert result.price == 10.12
    assert result.rating == 4.6
    assert result.name == "商品"


def test_normalize_preserves_other_fields() -> None:
    """正常场景：标准化不影响其他字段。"""
    p = make("P1", rank=5, review_count=100)
    result = DataCleaner().normalize([p])[0]
    assert result.product_id == "P1"
    assert result.rank == 5
    assert result.review_count == 100
    assert result.platform == "亚马逊"
    assert result.industry == "宠物用品"


def test_normalize_does_not_mutate_original() -> None:
    """正常场景：标准化不修改原对象。"""
    cleaner = DataCleaner()
    p = make("P1", price=10.123, rating=4.567, name=" 商品 ")
    original_price = p.price
    cleaner.normalize([p])
    assert p.price == original_price


def test_sort_by_rank() -> None:
    """正常场景：按 rank 升序排序。"""
    products = [make("P3", rank=3), make("P1", rank=1), make("P2", rank=2)]
    result = DataCleaner().sort_by_rank(products)
    assert [p.product_id for p in result] == ["P1", "P2", "P3"]


def test_clean_full() -> None:
    """正常场景：完整清洗（去重+标准化+排序）。"""
    cleaner = DataCleaner()
    products = [
        make("P2", rank=2, price=10.123, rating=4.567, name=" 商品2 "),
        make("P1", rank=1, price=20.0, rating=4.0),
        make("P2", rank=3, price=30.0, rating=3.0),
    ]
    cleaned = cleaner.clean(products)
    assert len(cleaned) == 2
    assert cleaned[0].product_id == "P1"
    assert cleaned[1].product_id == "P2"
    assert cleaned[1].price == 10.12
    assert cleaned[1].name == "商品2"


def test_clean_empty() -> None:
    """边界场景：空列表返回空。"""
    assert DataCleaner().clean([]) == []


def test_clean_single() -> None:
    """边界场景：单元素正常返回。"""
    p = make("P1")
    assert DataCleaner().clean([p])[0].product_id == "P1"


def test_clean_no_duplicates() -> None:
    """正常场景：无重复数据正常清洗。"""
    products = [make("P2", rank=2), make("P1", rank=1)]
    cleaned = DataCleaner().clean(products)
    assert len(cleaned) == 2
    assert cleaned[0].product_id == "P1"
