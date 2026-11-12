"""采集器基类与统一数据结构。

定义所有平台采集器共用的 ProductData 模型和 BaseCollector 抽象基类。
采集流程是确定性的（无 LLM），本模块只负责数据结构与接口约束。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

# 本项目支持的平台
PLATFORMS = ("亚马逊", "Walmart", "eBay")


class ProductData(BaseModel):
    """统一商品数据结构，对应选品池表字段。

    采集器产出此结构，后续清洗/Agent 分析均基于此。
    """

    product_id: str = Field(description="平台商品唯一 ID")
    name: str = Field(description="商品名称")
    industry: str = Field(description="所属行业")
    platform: str = Field(description="平台：亚马逊/Walmart/eBay")
    price: float = Field(description="售价（美元）")
    rating: float = Field(description="评分（0-5）")
    review_count: int = Field(description="评论数")
    rank: int = Field(description="品类排名")
    url: str = Field(description="商品链接")
    collected_at: datetime = Field(default_factory=datetime.now, description="采集时间")

    @field_validator("platform")
    @classmethod
    def _platform_valid(cls, v: str) -> str:
        if v not in PLATFORMS:
            raise ValueError(f"平台必须是 {PLATFORMS} 之一，收到: {v}")
        return v

    @field_validator("rating")
    @classmethod
    def _rating_valid(cls, v: float) -> float:
        if not (0 <= v <= 5):
            raise ValueError(f"评分必须在 0-5 之间，收到: {v}")
        return v

    @field_validator("price")
    @classmethod
    def _price_valid(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"价格必须大于 0，收到: {v}")
        return v

    @field_validator("review_count", "rank")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"评论数/排名不能为负，收到: {v}")
        return v


class BaseCollector(ABC):
    """采集器抽象基类。

    子类实现 collect()，返回 List[ProductData]。
    真实接口与 Mock 采集器均继承此基类，保证接口一致。
    """

    # 子类必须覆盖：平台标识
    platform: str = ""

    @abstractmethod
    def collect(self, industry: str, count: int) -> list[ProductData]:
        """采集指定行业的若干商品。

        Args:
            industry: 行业关键词（如 "宠物用品"）
            count: 采集数量

        Returns:
            商品列表，长度应 <= count
        """
        ...

    def _make_product(
        self,
        *,
        product_id: str,
        name: str,
        industry: str,
        price: float,
        rating: float,
        review_count: int,
        rank: int,
        url: str,
        collected_at: datetime | None = None,
    ) -> ProductData:
        """构造 ProductData，自动填充 platform 和采集时间。"""
        return ProductData(
            product_id=product_id,
            name=name,
            industry=industry,
            platform=self.platform,
            price=price,
            rating=rating,
            review_count=review_count,
            rank=rank,
            url=url,
            collected_at=collected_at or datetime.now(),
        )
