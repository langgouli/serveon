"""数据访问层：MySQL 优先，mock_data 兜底。

统一连接 127.0.0.1:3306 root/root 库 ziyan。
首次调用探测 MySQL 可用性，不可用则全程回退 mock_data，保证离线测试可跑。
返回结构与 mock_data 一致，消费方无需关心数据来源。
"""
from __future__ import annotations

import json
from typing import Optional

import pymysql

from app.tools.mock_data import (
    get_logistics as _mock_logistics,
    get_order as _mock_order,
    get_orders_by_user as _mock_by_user,
    get_recent_orders as _mock_recent,
    POLICIES as _MOCK_POLICIES,
    search_policies as _mock_search,
)

_HOST = "127.0.0.1"
_PORT = 3306
_USER = "root"
_PASSWORD = "root"
_DB = "ziyan"


def _row_to_order(r: tuple) -> dict:
    signed_at = r[6].isoformat() if r[6] else None
    return {
        "order_number": r[0],
        "user_id": r[1],
        "amount": float(r[2]),
        "product": r[3],
        "category": r[4],
        "status": r[5],
        "signed_at": signed_at,
        "support_return": bool(r[7]),
        "receiver_phone": "138****1234",
    }


class DataStore:
    """MySQL 优先、mock 兜底的数据存储。"""

    def __init__(self) -> None:
        self._conn: Optional[pymysql.connections.Connection] = None
        self._mysql_ok: Optional[bool] = None  # None=未探测

    # ---- 连接 ----
    def _connect(self) -> bool:
        if self._mysql_ok is None:
            try:
                self._conn = pymysql.connect(
                    host=_HOST, port=_PORT, user=_USER,
                    password=_PASSWORD, database=_DB,
                    charset="utf8mb4", connect_timeout=3,
                )
                self._mysql_ok = True
            except Exception:
                self._mysql_ok = False
        return self._mysql_ok

    def _query(self, sql: str, args: tuple = ()) -> list[tuple]:
        if not self._connect():
            raise RuntimeError("mysql unavailable")
        with self._conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()

    def _execute(self, sql: str, args: tuple = ()) -> bool:
        """写入（INSERT/UPDATE），失败返回 False 不抛异常（离线环境静默跳过）。"""
        if not self._connect():
            return False
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, args)
            self._conn.commit()
            return True
        except Exception:
            try:
                self._conn.rollback()
            except Exception:
                pass
            return False

    # ---- 退款记录 ----
    def save_refund(self, refund_info: dict) -> bool:
        """落库退款记录（幂等：同会话+订单先删旧记录）。离线/MySQL 不可用时静默返回 False。"""
        session_id = refund_info.get("session_id", "") or "-"
        order_number = refund_info.get("order_number", "")
        if not session_id or not order_number:
            return False
        record = refund_info.get("refund_record", {}) or {}
        status = refund_info.get("_refund_status") or record.get("status") or "processing"
        return self._execute(
            "DELETE FROM refunds WHERE session_id=%s AND order_number=%s",
            (session_id, order_number),
        ) and self._execute(
            "INSERT INTO refunds (session_id, order_number, user_id, request_type, amount, "
            "reason, refund_status, refund_no, refund_record, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())",
            (
                session_id, order_number,
                refund_info.get("user_id"),
                refund_info.get("request_type", "REFUND"),
                refund_info.get("amount", 0),
                refund_info.get("reason"),
                status,
                record.get("refund_no"),
                json.dumps(record, ensure_ascii=False, default=str),
            ),
        )

    def get_refund(self, session_id: str, order_number: str) -> Optional[dict]:
        """按会话+订单查最近退款记录；MySQL 不可用时返回 None（由内存槽位兜底）。"""
        if not self._connect():
            return None
        try:
            rows = self._query(
                "SELECT refund_status, refund_record FROM refunds "
                "WHERE session_id=%s AND order_number=%s ORDER BY created_at DESC LIMIT 1",
                (session_id, order_number),
            )
            if not rows:
                return None
            status, raw = rows[0]
            return {"_refund_status": status, "refund_record": json.loads(raw) if raw else {}}
        except Exception:
            return None

    def get_refund_by_order(self, order_number: str, limit: int = 1) -> list[dict]:
        """按订单号跨会话查下单记录（售后状态查询不依赖单号/会话）。"""
        if not self._connect():
            return []
        try:
            rows = self._query(
                "SELECT refund_status, refund_record FROM refunds "
                "WHERE order_number=%s ORDER BY created_at DESC LIMIT %s",
                (order_number, limit),
            )
            out = []
            for status, raw in rows:
                out.append({"_refund_status": status, "refund_record": json.loads(raw) if raw else {}})
            return out
        except Exception:
            return []

    # ---- 订单 ----
    def get_order(self, order_number: str) -> Optional[dict]:
        if self._connect():
            try:
                rows = self._query(
                    "SELECT order_number,user_id,amount,product,category,status,signed_at,support_return "
                    "FROM orders WHERE order_number=%s",
                    (order_number,),
                )
                if rows:
                    return _row_to_order(rows[0])
                return None
            except Exception:
                pass
        return _mock_order(order_number)

    def get_orders_by_user(self, user_id: int) -> list[dict]:
        if self._connect():
            try:
                rows = self._query(
                    "SELECT order_number,user_id,amount,product,category,status,signed_at,support_return "
                    "FROM orders WHERE user_id=%s ORDER BY order_number",
                    (user_id,),
                )
                return [_row_to_order(r) for r in rows]
            except Exception:
                pass
        return _mock_by_user(user_id)

    def get_recent_orders(self, user_id: int, limit: int = 5) -> list[dict]:
        return self.get_orders_by_user(user_id)[:limit]

    # ---- 物流 ----
    def get_logistics(self, order_number: str) -> Optional[dict]:
        if self._connect():
            try:
                rows = self._query(
                    "SELECT tracks,estimated_delivery,abnormal FROM logistics WHERE order_number=%s",
                    (order_number,),
                )
                if rows:
                    t, ed, ab = rows[0]
                    return {
                        "tracks": json.loads(t),
                        "estimated_delivery": ed.isoformat() if ed else None,
                        "abnormal": bool(ab),
                    }
                return None
            except Exception:
                pass
        return _mock_logistics(order_number)

    # ---- 政策 ----
    def get_policies(self) -> list[dict]:
        if self._connect():
            try:
                rows = self._query(
                    "SELECT clause_id,title,category,content,keywords FROM policies ORDER BY clause_id"
                )
                return [
                    {
                        "clause_id": r[0], "title": r[1], "category": r[2],
                        "content": r[3], "keywords": r[4].split(",") if r[4] else [],
                    }
                    for r in rows
                ]
            except Exception:
                pass
        return [dict(p) for p in _MOCK_POLICIES]

    def search_policies(self, query: str, top_k: int = 3) -> list[dict]:
        if self._connect():
            try:
                rows = self._query(
                    "SELECT clause_id,title,category,content,keywords FROM policies"
                )
                clauses = [
                    {
                        "clause_id": r[0], "title": r[1], "category": r[2],
                        "content": r[3], "keywords": r[4].split(",") if r[4] else [],
                    }
                    for r in rows
                ]
                results = []
                for c in clauses:
                    hits = sum(1 for kw in c["keywords"] if kw in query)
                    if hits > 0:
                        results.append((hits, c))
                results.sort(key=lambda x: -x[0])
                return [c for _, c in results[:top_k]]
            except Exception:
                pass
        return _mock_search(query, top_k=top_k)


_store: Optional[DataStore] = None


def get_store() -> DataStore:
    global _store
    if _store is None:
        _store = DataStore()
    return _store
