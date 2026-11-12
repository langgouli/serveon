"""获取机器人所在的群列表。"""

from src.feishu.auth import get_tenant_access_token
import httpx


def get_chat_list():
    """获取机器人所在的群列表。"""
    print("=== 获取机器人所在的群列表 ===\n")

    try:
        token = get_tenant_access_token()
        print(f"[OK] 获取token成功: {token[:20]}...")

        response = httpx.get(
            "https://open.feishu.cn/open-apis/im/v1/chats",
            headers={"Authorization": f"Bearer {token}"},
            params={"page_size": 100},
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                chats = data.get("data", {}).get("items", [])
                if not chats:
                    print("\n[警告] 机器人还未添加到任何群聊")
                    print("请先将应用添加到群聊：")
                    print("1. 打开飞书群聊")
                    print("2. 点击群名称 → 设置 → 群机器人")
                    print("3. 添加已发布的应用")
                else:
                    print(f"\n找到 {len(chats)} 个群聊：\n")
                    for i, chat in enumerate(chats, 1):
                        chat_id = chat.get("chat_id", "")
                        name = chat.get("name", "")
                        description = chat.get("description", "")
                        print(f"{i}. 群名称: {name}")
                        print(f"   chat_id: {chat_id}")
                        if description:
                            print(f"   描述: {description}")
                        print()
                    print("请将需要的 chat_id 配置到 .env 的 FEISHU_CHAT_ID 字段")
            else:
                print(f"[ERROR] API错误: code={data.get('code')}, msg={data.get('msg')}")
        else:
            print(f"[ERROR] HTTP错误: {response.status_code}")
            print(f"响应体: {response.text[:500]}")
    except Exception as e:
        print(f"[ERROR] 获取失败: {e}")


if __name__ == "__main__":
    get_chat_list()
