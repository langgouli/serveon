"""验证4张表的连通性。

测试步骤：
1. 获取tenant_access_token
2. 对每张表：查询字段、查询记录
"""

import httpx
from src.config import settings
from src.feishu.auth import FEISHU_BASE_URL, feishu_auth


def test_all_tables():
    """测试4张表的连通性。"""
    print("=== 4张表连通性测试 ===\n")

    # 1. 获取token
    print("1. 获取tenant_access_token...")
    try:
        token = feishu_auth.get_token()
        print(f"   [OK] token获取成功: {token[:20]}...")
    except Exception as e:
        print(f"   [ERROR] token获取失败: {e}")
        return False

    app_token = settings.feishu_bitable_app_token
    tables = {
        "采集配置": settings.feishu_table_id_collection_config,
        "选品池": settings.feishu_table_id_selection,
        "评论库": settings.feishu_table_id_review,
        "分析报告": settings.feishu_table_id_report,
    }

    all_ok = True
    for name, table_id in tables.items():
        if not table_id:
            print(f"\n[{name}] table_id未配置")
            all_ok = False
            continue

        # 去掉可能的多余字符
        table_id = table_id.split("&")[0].strip()

        print(f"\n[{name}] table_id: {table_id}")

        # 2. 查询字段
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        try:
            response = httpx.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                timeout=30,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    items = data.get("data", {}).get("items", [])
                    print(f"   [OK] 字段列表获取成功，共 {len(items)} 个字段")
                else:
                    print(f"   [ERROR] 飞书API错误: code={data.get('code')}, msg={data.get('msg')}")
                    all_ok = False
            else:
                print(f"   [ERROR] HTTP错误: {response.status_code}")
                all_ok = False
        except httpx.HTTPError as e:
            print(f"   [ERROR] 请求失败: {e}")
            all_ok = False

        # 3. 查询记录
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records/search"
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
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    items = data.get("data", {}).get("items", [])
                    print(f"   [OK] 记录查询成功，共 {len(items)} 条记录")
                else:
                    print(f"   [ERROR] 飞书API错误: code={data.get('code')}, msg={data.get('msg')}")
                    all_ok = False
            else:
                print(f"   [ERROR] HTTP错误: {response.status_code}")
                all_ok = False
        except httpx.HTTPError as e:
            print(f"   [ERROR] 请求失败: {e}")
            all_ok = False

    print("\n=== 测试完成 ===")
    if all_ok:
        print("[OK] 所有表连通正常")
    else:
        print("[ERROR] 部分表存在问题")
    return all_ok


if __name__ == "__main__":
    test_all_tables()
