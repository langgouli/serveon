"""测试火山方舟AI模型连接。"""

from src.config import settings
from src.ai.model_router import get_model_router


def test_ai_connection():
    """测试AI模型连接。"""
    print("=== 火山方舟AI模型连接测试 ===\n")

    # 1. 检查配置
    print("1. 检查配置...")
    print(f"   API Key: {settings.openai_api_key[:20]}...")
    print(f"   API Base: {settings.openai_api_base}")

    # 2. 初始化模型路由器
    print("\n2. 初始化模型路由器...")
    try:
        router = get_model_router()
        print("   [OK] 模型路由器初始化成功")
    except Exception as e:
        print(f"   [ERROR] 初始化失败: {e}")
        return False

    # 3. 获取LLM
    print("\n3. 获取LLM实例...")
    try:
        llm = router.get_llm("standard")
        print(f"   [OK] LLM获取成功")
        print(f"   模型类型: {type(llm).__name__}")
    except Exception as e:
        print(f"   [ERROR] LLM获取失败: {e}")
        return False

    # 4. 测试调用
    print("\n4. 测试LLM调用...")
    try:
        from langchain_core.messages import HumanMessage

        response = llm.invoke([HumanMessage(content="你好，请回复'测试成功'")])
        print(f"   [OK] LLM调用成功")
        print(f"   响应: {response.content[:50]}...")
        return True
    except Exception as e:
        print(f"   [ERROR] LLM调用失败: {e}")
        return False


if __name__ == "__main__":
    test_ai_connection()
