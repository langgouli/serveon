"""任务控制页：手动触发采集和分析任务。

提供按钮让用户手动执行：
1. 选品数据采集
2. 选品策略分析
3. 数据清理

执行结果显示在日志区域。
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.observability.logger import get_logger

logger = get_logger()


class TaskWorker(QThread):
    """后台任务线程。"""

    log_signal = Signal(str)
    result_signal = Signal(dict)

    def __init__(self, task_func, task_name: str) -> None:
        super().__init__()
        self.task_func = task_func
        self.task_name = task_name

    def run(self) -> None:
        """执行任务。"""
        self.log_signal.emit(f"开始执行: {self.task_name}")
        try:
            result = self.task_func()
            self.log_signal.emit(f"{self.task_name} 完成: {result}")
            self.result_signal.emit(result)
        except Exception as e:
            self.log_signal.emit(f"{self.task_name} 失败: {e}")
            self.result_signal.emit({"status": "error", "error": str(e)})


class TaskPage(QWidget):
    """任务控制页。"""

    def __init__(self) -> None:
        super().__init__()
        self._current_worker: TaskWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        """初始化 UI。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)

        # 标题
        title = QLabel("任务控制")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #303133;")
        layout.addWidget(title)

        # 任务按钮区
        task_group = QGroupBox("手动执行任务")
        task_layout = QHBoxLayout(task_group)

        self.collect_btn = QPushButton("📥 选品数据采集")
        self.analyze_btn = QPushButton("🤖 选品策略分析")
        self.cleanup_btn = QPushButton("🗑️ 数据清理")

        self.collect_btn.clicked.connect(self._run_collection)
        self.analyze_btn.clicked.connect(self._run_analysis)
        self.cleanup_btn.clicked.connect(self._run_cleanup)

        task_layout.addWidget(self.collect_btn)
        task_layout.addWidget(self.analyze_btn)
        task_layout.addWidget(self.cleanup_btn)
        task_layout.addStretch()

        layout.addWidget(task_group)

        # 日志区域
        log_group = QGroupBox("执行日志")
        log_layout = QVBoxLayout(log_group)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumBlockCount(1000)
        log_layout.addWidget(self.log_edit)

        layout.addWidget(log_group, stretch=1)

    def _run_collection(self) -> None:
        """执行采集任务。"""
        from src.scheduler.tasks import product_collection_task
        self._run_task(product_collection_task, "选品数据采集")

    def _run_analysis(self) -> None:
        """执行分析任务。"""
        from src.scheduler.tasks import selection_analysis_task
        self._run_task(selection_analysis_task, "选品策略分析")

    def _run_cleanup(self) -> None:
        """执行清理任务。"""
        from src.scheduler.tasks import data_cleanup_task
        self._run_task(data_cleanup_task, "数据清理")

    def _run_task(self, task_func, task_name: str) -> None:
        """执行通用任务。"""
        if self._current_worker is not None and self._current_worker.isRunning():
            self.log_edit.appendPlainText("⚠️ 当前有任务正在执行，请等待完成")
            return

        self._current_worker = TaskWorker(task_func, task_name)
        self._current_worker.log_signal.connect(self._append_log)
        self._current_worker.result_signal.connect(self._on_task_result)
        self._current_worker.start()

    def _append_log(self, text: str) -> None:
        """追加日志。"""
        self.log_edit.appendPlainText(f"[{text}]")

    def _on_task_result(self, result: dict) -> None:
        """任务完成回调。"""
        self._current_worker = None
        status = result.get("status", "未知")
        if status == "success":
            self.log_edit.appendPlainText(f"✅ 任务成功: {result}")
        elif status == "skipped":
            self.log_edit.appendPlainText(f"⏭️ 任务跳过: {result}")
        else:
            self.log_edit.appendPlainText(f"❌ 任务失败: {result}")
