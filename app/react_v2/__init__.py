"""ReAct v2 独立模块（影子灰度期）：

- 主 ReAct Agent（总循环 + 8 个确定性工具 + 信封协议）
- 情绪识别回复 Agent（与业务并行，超时降级、异常隔离）
- 对外暴露 chat(session_id, user_message)（签名与 app.main.chat 一致）

只 import 现有代码（工具函数/服务类），不修改任何现有文件。
"""
from .react_loop import chat_v2

chat = chat_v2  # 对外统一入口别名

__all__ = ["chat", "chat_v2"]
