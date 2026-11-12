"""调度器模块。

导出：
- SchedulerManager: 调度器管理器
- product_collection_task: 选品数据采集任务
- selection_analysis_task: 选品策略分析任务
- data_cleanup_task: 数据清理任务
- ALL_TRIGGERS: 所有触发器配置
"""

from src.scheduler.scheduler import SchedulerManager
from src.scheduler.tasks import (
    data_cleanup_task,
    product_collection_task,
    selection_analysis_task,
)
from src.scheduler.triggers import ALL_TRIGGERS

__all__ = [
    "SchedulerManager",
    "product_collection_task",
    "selection_analysis_task",
    "data_cleanup_task",
    "ALL_TRIGGERS",
]
