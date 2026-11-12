"""飞书API连通性测试脚本。

测试步骤：
1. 检查飞书API基础URL连通性
2. 测试获取tenant_access_token
3. 打印创建表的请求URL格式
"""

import httpx
from src.config import settings
from src.feishu.auth import FEISHU_BASE_URL, feishu_auth


def test_connectivity():
    """测试飞书API连通性。"""
    print("=== 飞书API连通性测试 ===\n")

    # 1. 测试基础URL连通性
    print("1. 测试基础URL连通性...")
    try:
        response = httpx.get(FEISHU_BASE_URL, timeout=10)
        print(f"   [OK] 基础URL可访问: {FEISHU_BASE_URL}")
        print(f"   状态码: {response.status_code}")
    except httpx.HTTPError as e:
        print(f"   [ERROR] 基础URL不可访问: {e}")
        return False

    # 2. 测试获取token
    print("\n2. 测试获取tenant_access_token...")
    try:
        token = feishu_auth.get_token()
        print(f"   [OK] token获取成功: {token[:20]}...")
        print(f"   完整长度: {len(token)} 字符")
    except Exception as e:
        print(f"   [ERROR] token获取失败: {e}")
        return False

    # 3. 打印创建表的请求URL
    print("\n3. 创建表的请求URL格式...")
    app_token = settings.feishu_bitable_app_token
    table_url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables"
    print(f"   请求URL: {table_url}")
    print(f"   App Token: {app_token}")

    # 4. 测试创建表API（会返回403，但可以验证URL格式）
    print("\n4. 测试创建表API（预期403）...")
    try:
        response = httpx.post(
            table_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "table": {
                    "name": "测试表",
                    "fields": [{"field_name": "测试字段", "type": 1}],
                }
            },
            timeout=30,
        )
        print(f"   状态码: {response.status_code}")
        if response.status_code == 403:
            print("   [警告] 预期的403错误（权限问题）")
            print("   需要完成以下操作：")
            print("   1. 在飞书开放平台启用 bitable:app 权限")
            print("   2. 发布新版本并等待生效")
            print("   3. 将应用添加为表格协作者（编辑权限）")
        else:
            print(f"   响应: {response.text[:200]}")
    except httpx.HTTPError as e:
        print(f"   [ERROR] 请求失败: {e}")

    print("\n=== 测试完成 ===")
    return True


if __name__ == "__main__":
    test_connectivity()
