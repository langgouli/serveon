"""Task 2.2 增量同步服务测试。

用 FakeBitable 模拟飞书表，验证增量去重逻辑。
覆盖：正常（全新增/混合/评论/报告）、边界（空输入）、异常（更新失败）。
"""

from __future__ import annotations

from src.feishu.sync_service import SyncResult, SyncService
from src.pipeline.collectors.base import ProductData


def make_product(
    pid: str, platform: str = "亚马逊", price: float = 10.0
) -> ProductData:
    return ProductData(
        product_id=pid, name=f"商品{pid}", industry="宠物用品", platform=platform,
        price=price, rating=4.0, review_count=100, rank=1,
        url=f"https://example.com/{pid}",
    )


class FakeBitable:
    """模拟飞书 bitable，支持查询/批量新增/更新。"""

    def __init__(
        self,
        existing_records: list[dict] | None = None,
        fail_update_ids: set[str] | None = None,
    ) -> None:
        self._records = list(existing_records or [])
        self._id_counter = 0
        self.batch_added: list[dict] = []
        self.updated: list[tuple[str, dict]] = []
        self._fail_update = set(fail_update_ids or [])

    def query_records(self, table_id, filter_condition=None, page_size=100):
        return list(self._records)

    def batch_add_records(self, table_id, records):
        self.batch_added.extend(records)
        ids = []
        for r in records:
            self._id_counter += 1
            rid = f"rec{self._id_counter}"
            ids.append(rid)
            self._records.append({"record_id": rid, "fields": dict(r)})
        return ids

    def update_record(self, table_id, record_id, fields):
        if record_id in self._fail_update:
            raise RuntimeError("更新失败")
        self.updated.append((record_id, fields))
        for r in self._records:
            if r["record_id"] == record_id:
                r["fields"].update(fields)
        return record_id


def test_sync_products_all_new() -> None:
    """正常场景：全部新增。"""
    fake = FakeBitable()
    svc = SyncService("t1", "选品池", bitable=fake)
    result = svc.sync_products([make_product("P1"), make_product("P2")])
    assert result.new_count == 2
    assert result.update_count == 0
    assert result.fail_count == 0
    assert len(fake.batch_added) == 2


def test_sync_products_mixed() -> None:
    """正常场景：部分新增部分更新。"""
    fake = FakeBitable(
        existing_records=[
            {"record_id": "rec_existing", "fields": {"商品ID": "P1", "平台": "亚马逊"}},
        ]
    )
    svc = SyncService("t1", "选品池", bitable=fake)
    result = svc.sync_products([make_product("P1"), make_product("P2")])
    assert result.new_count == 1
    assert result.update_count == 1
    assert len(fake.batch_added) == 1
    assert len(fake.updated) == 1


def test_sync_products_empty() -> None:
    """边界场景：空输入返回空统计。"""
    fake = FakeBitable()
    svc = SyncService("t1", "选品池", bitable=fake)
    result = svc.sync_products([])
    assert result.new_count == 0
    assert result.total == 0
    assert fake.batch_added == []


def test_sync_products_update_failure() -> None:
    """异常场景：更新失败计入 fail_count。"""
    fake = FakeBitable(
        existing_records=[
            {"record_id": "rec_existing", "fields": {"商品ID": "P1", "平台": "亚马逊"}},
        ],
        fail_update_ids={"rec_existing"},
    )
    svc = SyncService("t1", "选品池", bitable=fake)
    result = svc.sync_products([make_product("P1")])
    assert result.update_count == 0
    assert result.fail_count == 1
    assert len(result.errors) == 1


def test_sync_reviews() -> None:
    """正常场景：评论同步。"""
    fake = FakeBitable()
    svc = SyncService("t1", "评论库", bitable=fake)
    reviews = [
        {"评论ID": "R1", "商品ID": "P1", "评论内容": "好", "评分": 5},
        {"评论ID": "R2", "商品ID": "P1", "评论内容": "差", "评分": 1},
    ]
    result = svc.sync_reviews(reviews)
    assert result.new_count == 2


def test_sync_reports() -> None:
    """正常场景：报告同步。"""
    fake = FakeBitable()
    svc = SyncService("t1", "分析报告", bitable=fake)
    reports = [
        {"报告ID": "REP1", "行业": "宠物用品", "平台": "亚马逊", "决策": "强烈推荐"},
    ]
    result = svc.sync_reports(reports)
    assert result.new_count == 1


def test_sync_records_empty() -> None:
    """边界场景：空记录同步返回空统计。"""
    fake = FakeBitable()
    svc = SyncService("t1", "评论库", bitable=fake)
    result = svc.sync_records([], ["评论ID"])
    assert result.new_count == 0


def test_sync_records_mixed() -> None:
    """正常场景：评论同步混合新增/更新。"""
    fake = FakeBitable(
        existing_records=[{"record_id": "rec_r1", "fields": {"评论ID": "R1"}}]
    )
    svc = SyncService("t1", "评论库", bitable=fake)
    reviews = [
        {"评论ID": "R1", "评论内容": "更新"},
        {"评论ID": "R2", "评论内容": "新增"},
    ]
    result = svc.sync_reviews(reviews)
    assert result.new_count == 1
    assert result.update_count == 1


def test_sync_result_str() -> None:
    """正常场景：SyncResult 字符串格式。"""
    r = SyncResult(
        table_name="选品池", new_count=1, update_count=2,
        skip_count=3, duration_ms=100,
    )
    s = str(r)
    assert "选品池" in s
    assert "新增 1" in s


def test_sync_result_total() -> None:
    """正常场景：total 为四项之和。"""
    r = SyncResult(new_count=1, update_count=2, skip_count=3, fail_count=4)
    assert r.total == 10


def test_extract_product_primary() -> None:
    """正常场景：商品主键提取。"""
    p = make_product("P1", platform="eBay")
    assert SyncService._extract_product_primary(p) == ("P1", "eBay")


def test_build_existing_index() -> None:
    """正常场景：构建主键索引。"""
    fake = FakeBitable(
        existing_records=[
            {"record_id": "rec1", "fields": {"商品ID": "P1", "平台": "亚马逊"}},
            {"record_id": "rec2", "fields": {"商品ID": "P2", "平台": "eBay"}},
        ]
    )
    svc = SyncService("t1", "选品池", bitable=fake)
    index = svc._build_existing_index(["商品ID", "平台"])
    assert ("P1", "亚马逊") in index
    assert ("P2", "eBay") in index


def test_sync_products_platform_dict_format() -> None:
    """正常场景：飞书单选字段 dict 格式主键匹配。"""
    fake = FakeBitable(
        existing_records=[
            {
                "record_id": "rec1",
                "fields": {"商品ID": "P1", "平台": {"name": "亚马逊"}},
            },
        ]
    )
    svc = SyncService("t1", "选品池", bitable=fake)
    result = svc.sync_products([make_product("P1", platform="亚马逊")])
    assert result.update_count == 1
    assert result.new_count == 0
