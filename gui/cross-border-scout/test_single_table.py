"""单表测试脚本：测试对指定表的操作。

测试步骤：
1. 获取tenant_access_token
2. 列出表的所有字段
3. 查询表中的记录
"""

import httpx
from src.config import settings
from src.feishu.auth import FEISHU_BASE_URL, feishu_auth


def test_single_table():
    """测试单表操作。"""
    print("=== 单表测试 ===\n")

    # 1. 获取token
    print("1. 获取tenant_access_token...")
    try:
        token = feishu_auth.get_token()
        print(f"   [OK] token获取成功: {token[:20]}...")
    except Exception as e:
        print(f"   [ERROR] token获取失败: {e}")
        return False

    # 2. 列出表的字段
    print("\n2. 列出表的所有字段...")
    app_token = settings.feishu_bitable_app_token
    table_id = settings.feishu_table_id_collection_config

    if not table_id:
        print("   [ERROR] 采集配置表的table_id未配置")
        return False

    # 去掉可能的多余字符
    table_id = table_id.split("&")[0].strip()

    url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
    print(f"   请求URL: {url}")

    try:
        response = httpx.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            timeout=30,
        )
        print(f"   状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                items = data.get("data", {}).get("items", [])
                print(f"   [OK] 字段列表获取成功，共 {len(items)} 个字段")
                for i, item in enumerate(items[:5], 1):
                    field_name = item.get("field_name", "")
                    field_type = item.get("type", "")
                    print(f"      {i}. {field_name} (type={field_type})")
                if len(items) > 5:
                    print(f"      ... 还有 {len(items) - 5} 个字段")
            else:
                print(f"   [ERROR] 飞书API错误: code={data.get('code')}, msg={data.get('msg')}")
                return False
        else:
            print(f"   [ERROR] HTTP错误: {response.status_code}")
            print(f"   响应体: {response.text[:500]}")
            return False
    except httpx.HTTPError as e:
        print(f"   [ERROR] 请求失败: {e}")
        return False

    # 3. 查询表中的记录
    print("\n3. 查询表中的记录...")
    url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records/search"
    print(f"   请求URL: {url}")

    try:
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={"page_size": 10},
            timeout=30,
        )
        print(f"   状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                items = data.get("data", {}).get("items", [])
                print(f"   [OK] 记录查询成功，共 {len(items)} 条记录")
                for i, item in enumerate(items[:3], 1):
                    fields = item.get("fields", {})
                    print(f"      {i}. {list(fields.keys())[:3]}...")
            else:
                print(f"   [ERROR] 飞书API错误: code={data.get('code')}, msg={data.get('msg')}")
        else:
            print(f"   [ERROR] HTTP错误: {response.status_code}")
            print(f"   响应体: {response.text[:500]}")
    except httpx.HTTPError as e:
        print(f"   [ERROR] 请求失败: {e}")

    print("\n=== 测试完成 ===")
    return True


if __name__ == "__main__":
    test_single_table()
