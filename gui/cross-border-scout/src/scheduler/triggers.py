"""触发器配置：集中管理所有定时任务的 cron 表达式。

APScheduler cron 表达式格式：
  minute hour day month day_of_week
  0-59   0-23 1-31 1-12 0-6 (0=周一, 6=周日)
"""

from __future__ import annotations


# 选品数据采集：每天 09:00
COLLECTION_TRIGGER = {
    "trigger": "cron",
    "hour": 9,
    "minute": 0,
    "id": "product_collection",
    "name": "选品数据采集",
}

# 选品策略分析：每天 18:00（用户要求默认每日18:00推送报告）
SELECTION_ANALYSIS_TRIGGER = {
    "trigger": "cron",
    "hour": 18,
    "minute": 0,
    "id": "selection_analysis",
    "name": "选品策略分析",
}

# 数据清理：每三天凌晨 2 点执行
DATA_CLEANUP_TRIGGER = {
    "trigger": "cron",
    "day": "*/3",  # 每 3 天
    "hour": 2,
    "minute": 0,
    "id": "data_cleanup",
    "name": "数据清理",
}

# 所有触发器汇总
ALL_TRIGGERS = [
    COLLECTION_TRIGGER,
    SELECTION_ANALYSIS_TRIGGER,
    DATA_CLEANUP_TRIGGER,
]
