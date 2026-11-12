# 跨境电商选品策略平台

基于 LangGraph 的跨境电商选品策略分析平台，自动采集商品数据、分析选品机会、生成策略报告并推送飞书。

## 功能特性

- **数据采集**：支持亚马逊、Walmart、eBay 三平台商品数据采集
- **选品分析**：基于 LLM 的四角度分析 + 六维度评分 + 决策矩阵
- **报告推送**：自动生成选品策略报告卡片推送到飞书群
- **定时调度**：每日采集、每日分析、定期清理
- **GUI 控制**：可视化配置、手动触发、数据看板、健康检查

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 .env

复制 `.env.example` 为 `.env`，填写飞书凭证和 AI 模型配置。

### 3. 初始化飞书表格

```bash
python -m src.feishu.init_tables
```

### 4. 启动 GUI

```bash
python -m src.main
```

### 5. 启动调度器（命令行模式）

```bash
python -m src.scheduler.scheduler
```

## 项目结构

```
src/
├── config.py              # 配置中心
├── main.py                # 统一启动入口
├── ai/
│   ├── prompt_manager.py  # 选品策略 Prompt
│   ├── model_router.py    # 多模型路由
│   └── agents/
│       ├── selection_tools.py   # Agent 工具集
│       └── selection_agent.py   # ReAct Agent
├── pipeline/
│   ├── collectors/        # 数据采集器
│   ├── cleaners/          # 数据清洗
│   ├── collection_pipeline.py  # 采集流程
│   └── collection_runner.py    # 采集→同步
├── feishu/
│   ├── bitable.py         # 多维表格 API
│   ├── sync_service.py    # 增量同步服务
│   ├── card_templates.py  # 飞书卡片模板
│   ├── field_mapping.py   # 字段映射
│   ├── table_schema.py    # 表结构定义
│   └── init_tables.py     # 建表服务
├── scheduler/
│   ├── triggers.py        # 触发器配置
│   ├── tasks.py           # 定时任务
│   └── scheduler.py       # 调度器
├── gui/
│   ├── main_window.py     # 主窗口
│   └── pages/             # 配置/任务/看板/检查页
└── observability/
    ├── logger.py          # 日志
    ├── llm_monitor.py     # LLM 调用监控
    ├── metrics_store.py   # 指标存储
    └── alert.py           # 异常告警
```

## 测试

```bash
python -m pytest test/ -v
```

## 打包

```bash
pip install pyinstaller PySide6
python scripts/build_exe.py
```

输出：`dist/跨境电商选品策略平台.exe`

## 技术栈

- Python 3.14+
- LangGraph + LangChain Core
- PySide6 (GUI)
- APScheduler (调度)
- 飞书多维表格 API
