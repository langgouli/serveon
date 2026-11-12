"""初始化 ziyan 数据库：建库建表 + 从 mock_data 导入订单/物流/政策。

用法：
  python -m app.sql.init_db
连接：127.0.0.1 root/root
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pymysql

from app.tools.mock_data import LOGISTICS, ORDERS, POLICIES

HOST = "127.0.0.1"
PORT = 3306
USER = "root"
PASSWORD = "root"
DB = "ziyan"


def _signed_at(offset_days):
    if offset_days is None:
        return None
    return datetime.now() - timedelta(days=offset_days)


def main() -> None:
    conn = pymysql.connect(host=HOST, port=PORT, user=USER, password=PASSWORD, charset="utf8mb4")
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB} DEFAULT CHARSET utf8mb4")
        cur.execute(f"USE {DB}")
        # 建表（pymysql 无 executescript，逐条执行）
        ddl = open("app/sql/schema.sql", encoding="utf-8").read()
        for stmt in ddl.split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)

        # 订单
        for o in ORDERS.values():
            cur.execute(
                "INSERT INTO orders VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    o["order_number"], o["user_id"], o["amount"], o["product"],
                    o["category"], o["status"], _signed_at(o["signed_at_offset_days"]),
                    1 if o["support_return"] else 0,
                ),
            )

        # 物流
        for no, lg in LOGISTICS.items():
            cur.execute(
                "INSERT INTO logistics VALUES (%s,%s,%s,%s)",
                (
                    no,
                    json.dumps(lg["tracks"], ensure_ascii=False),
                    datetime.strptime(lg["estimated_delivery"], "%Y-%m-%d")
                    if lg["estimated_delivery"] else None,
                    1 if lg["abnormal"] else 0,
                ),
            )

        # 政策
        for p in POLICIES:
            cur.execute(
                "INSERT INTO policies VALUES (%s,%s,%s,%s,%s)",
                (
                    p["clause_id"], p["title"], p["category"],
                    p["content"], ",".join(p["keywords"]),
                ),
            )

        conn.commit()
        # 核对
        for t in ("orders", "logistics", "policies"):
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"{t}: {cur.fetchone()[0]} 行")
        cur.execute("SELECT order_number,amount,status FROM orders ORDER BY order_number")
        print("orders:", cur.fetchall())
        cur.execute("SELECT clause_id,title FROM policies ORDER BY clause_id")
        print("policies:", cur.fetchall())
    conn.close()


if __name__ == "__main__":
    main()
