"""测试飞书推送功能。"""

from src.feishu.feishu_bot import feishu_bot
from src.feishu.application_bot import application_bot


def test_feishu_push():
    """测试飞书推送功能。"""
    print("=== 飞书推送功能测试 ===\n")

    # 测试卡片
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "测试卡片"},
            "template": "blue",
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": "**测试内容**\n这是一条测试消息"}},
        ],
    }

    # 1. Webhook机器人测试
    print("1. 测试Webhook机器人...")
    if feishu_bot.is_configured:
        result = feishu_bot.send_card(card)
        print(f"   Webhook URL: {feishu_bot._webhook_url[:50]}...")
        print(f"   [OK] Webhook机器人推送成功" if result else f"   [ERROR] Webhook机器人推送失败")
    else:
        print("   [跳过] Webhook URL未配置")

    # 2. 应用机器人测试
    print("\n2. 测试应用机器人...")
    if application_bot.is_configured:
        result = application_bot.send_card(card)
        print(f"   chat_id: {application_bot._chat_id}")
        print(f"   [OK] 应用机器人推送成功" if result else f"   [ERROR] 应用机器人推送失败")
    else:
        print("   [跳过] chat_id未配置")

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_feishu_push()
