from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from threading import Lock
from typing import Any

from app.config import DB_PATH

_DB_LOCK = Lock()


def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    with _DB_LOCK:
        conn = get_connection()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS import_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_date TEXT NOT NULL,
                    source_image TEXT NOT NULL,
                    raw_payload TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS daily_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    report_date TEXT NOT NULL,
                    deal_count INTEGER NOT NULL,
                    high_intent_count INTEGER NOT NULL,
                    private_domain_new INTEGER NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0,
                    source_batch_id INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(employee_id, report_date),
                    FOREIGN KEY (employee_id) REFERENCES employees(id),
                    FOREIGN KEY (source_batch_id) REFERENCES import_batches(id)
                );
                """
            )
            conn.commit()
        finally:
            conn.close()


def create_import_batch(report_date: str, source_image: str, raw_payload: dict[str, Any], status: str) -> int:
    now = _utc_now()
    with _DB_LOCK:
        conn = get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO import_batches(report_date, source_image, raw_payload, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (report_date, source_image, json.dumps(raw_payload, ensure_ascii=False), status, now),
            )
            conn.commit()
            return int(cursor.lastrowid)
        finally:
            conn.close()


def _get_or_create_employee(conn: sqlite3.Connection, name: str) -> int:
    existing = conn.execute("SELECT id FROM employees WHERE name = ?", (name,)).fetchone()
    if existing:
        return int(existing["id"])

    cursor = conn.execute(
        "INSERT INTO employees(name, created_at) VALUES (?, ?)",
        (name, _utc_now()),
    )
    return int(cursor.lastrowid)


def upsert_daily_records(report_date: str, records: list[dict[str, Any]], source_batch_id: int | None = None) -> None:
    now = _utc_now()
    with _DB_LOCK:
        conn = get_connection()
        try:
            for item in records:
                employee_id = _get_or_create_employee(conn, str(item["employee_name"]).strip())
                conn.execute(
                    """
                    INSERT INTO daily_performance(
                        employee_id, report_date, deal_count, high_intent_count,
                        private_domain_new, confidence, source_batch_id, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(employee_id, report_date)
                    DO UPDATE SET
                        deal_count = excluded.deal_count,
                        high_intent_count = excluded.high_intent_count,
                        private_domain_new = excluded.private_domain_new,
                        confidence = excluded.confidence,
                        source_batch_id = excluded.source_batch_id,
                        updated_at = excluded.updated_at
                    """,
                    (
                        employee_id,
                        report_date,
                        int(item["deal_count"]),
                        int(item["high_intent_count"]),
                        int(item["private_domain_new"]),
                        float(item.get("confidence", 0.0)),
                        source_batch_id,
                        now,
                        now,
                    ),
                )
            conn.commit()
        finally:
            conn.close()


def _serialize_employee(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "created_at": row["created_at"],
    }


def list_employees(keyword: str | None = None) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        params: list[Any] = []
        where_sql = ""
        if keyword:
            where_sql = "WHERE e.name LIKE ?"
            params.append(f"%{keyword.strip()}%")

        rows = conn.execute(
            f"""
            SELECT
                e.id,
                e.name,
                e.created_at,
                COUNT(d.id) AS performance_count
            FROM employees e
            LEFT JOIN daily_performance d ON d.employee_id = e.id
            {where_sql}
            GROUP BY e.id
            ORDER BY e.id DESC
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            **_serialize_employee(row),
            "performance_count": int(row["performance_count"]),
        }
        for row in rows
    ]


def get_employee(employee_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, created_at FROM employees WHERE id = ?",
            (employee_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return None
    return _serialize_employee(row)


def create_employee(name: str) -> dict[str, Any]:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("员工姓名不能为空")

    with _DB_LOCK:
        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO employees(name, created_at) VALUES (?, ?)",
                (clean_name, _utc_now()),
            )
            conn.commit()
            created_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ValueError("员工姓名已存在") from exc
        finally:
            conn.close()

    employee = get_employee(created_id)
    if not employee:
        raise ValueError("员工创建失败")
    return employee


def update_employee(employee_id: int, name: str) -> dict[str, Any]:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("员工姓名不能为空")

    with _DB_LOCK:
        conn = get_connection()
        try:
            exists = conn.execute("SELECT 1 FROM employees WHERE id = ?", (employee_id,)).fetchone()
            if not exists:
                raise LookupError("员工不存在")

            conn.execute(
                "UPDATE employees SET name = ? WHERE id = ?",
                (clean_name, employee_id),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("员工姓名已存在") from exc
        finally:
            conn.close()

    employee = get_employee(employee_id)
    if not employee:
        raise LookupError("员工不存在")
    return employee


def delete_employee(employee_id: int) -> None:
    with _DB_LOCK:
        conn = get_connection()
        try:
            exists = conn.execute("SELECT 1 FROM employees WHERE id = ?", (employee_id,)).fetchone()
            if not exists:
                raise LookupError("员工不存在")

            perf_count = conn.execute(
                "SELECT COUNT(1) AS c FROM daily_performance WHERE employee_id = ?",
                (employee_id,),
            ).fetchone()
            if perf_count and int(perf_count["c"]) > 0:
                raise ValueError("该员工已有业绩记录，无法删除")

            conn.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
            conn.commit()
        finally:
            conn.close()


def _serialize_performance(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "employee_id": int(row["employee_id"]),
        "employee_name": row["employee_name"],
        "report_date": row["report_date"],
        "deal_count": int(row["deal_count"]),
        "high_intent_count": int(row["high_intent_count"]),
        "private_domain_new": int(row["private_domain_new"]),
        "confidence": float(row["confidence"]),
        "source_batch_id": row["source_batch_id"],
        "updated_at": row["updated_at"],
    }


def get_performance(performance_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT
                d.id,
                d.employee_id,
                e.name AS employee_name,
                d.report_date,
                d.deal_count,
                d.high_intent_count,
                d.private_domain_new,
                d.confidence,
                d.source_batch_id,
                d.updated_at
            FROM daily_performance d
            JOIN employees e ON e.id = d.employee_id
            WHERE d.id = ?
            """,
            (performance_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return None
    return _serialize_performance(row)


def list_performances(report_date: str | None = None, employee_id: int | None = None) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        conditions: list[str] = []
        params: list[Any] = []

        if report_date:
            conditions.append("d.report_date = ?")
            params.append(report_date)
        if employee_id:
            conditions.append("d.employee_id = ?")
            params.append(employee_id)

        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = conn.execute(
            f"""
            SELECT
                d.id,
                d.employee_id,
                e.name AS employee_name,
                d.report_date,
                d.deal_count,
                d.high_intent_count,
                d.private_domain_new,
                d.confidence,
                d.source_batch_id,
                d.updated_at
            FROM daily_performance d
            JOIN employees e ON e.id = d.employee_id
            {where_sql}
            ORDER BY d.report_date DESC, d.deal_count DESC, d.id DESC
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    return [_serialize_performance(row) for row in rows]


def create_performance(payload: dict[str, Any]) -> dict[str, Any]:
    employee_id = int(payload["employee_id"])
    report_date = str(payload["report_date"])
    deal_count = int(payload["deal_count"])
    high_intent_count = int(payload["high_intent_count"])
    private_domain_new = int(payload["private_domain_new"])
    confidence = float(payload.get("confidence", 1.0))

    if deal_count < 0 or high_intent_count < 0 or private_domain_new < 0:
        raise ValueError("业绩字段不能为负数")

    now = _utc_now()
    with _DB_LOCK:
        conn = get_connection()
        try:
            employee = conn.execute("SELECT 1 FROM employees WHERE id = ?", (employee_id,)).fetchone()
            if not employee:
                raise LookupError("员工不存在")

            cursor = conn.execute(
                """
                INSERT INTO daily_performance(
                    employee_id, report_date, deal_count, high_intent_count,
                    private_domain_new, confidence, source_batch_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    employee_id,
                    report_date,
                    deal_count,
                    high_intent_count,
                    private_domain_new,
                    confidence,
                    now,
                    now,
                ),
            )
            conn.commit()
            created_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ValueError("该员工该日期业绩已存在，请使用编辑") from exc
        finally:
            conn.close()

    created = get_performance(created_id)
    if not created:
        raise ValueError("业绩创建失败")
    return created


def update_performance(performance_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    employee_id = int(payload["employee_id"])
    report_date = str(payload["report_date"])
    deal_count = int(payload["deal_count"])
    high_intent_count = int(payload["high_intent_count"])
    private_domain_new = int(payload["private_domain_new"])
    confidence = float(payload.get("confidence", 1.0))

    if deal_count < 0 or high_intent_count < 0 or private_domain_new < 0:
        raise ValueError("业绩字段不能为负数")

    with _DB_LOCK:
        conn = get_connection()
        try:
            exists = conn.execute("SELECT 1 FROM daily_performance WHERE id = ?", (performance_id,)).fetchone()
            if not exists:
                raise LookupError("业绩记录不存在")

            employee = conn.execute("SELECT 1 FROM employees WHERE id = ?", (employee_id,)).fetchone()
            if not employee:
                raise LookupError("员工不存在")

            conn.execute(
                """
                UPDATE daily_performance
                SET employee_id = ?, report_date = ?, deal_count = ?, high_intent_count = ?,
                    private_domain_new = ?, confidence = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    employee_id,
                    report_date,
                    deal_count,
                    high_intent_count,
                    private_domain_new,
                    confidence,
                    _utc_now(),
                    performance_id,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("该员工该日期业绩已存在，请修改原记录") from exc
        finally:
            conn.close()

    updated = get_performance(performance_id)
    if not updated:
        raise LookupError("业绩记录不存在")
    return updated


def delete_performance(performance_id: int) -> None:
    with _DB_LOCK:
        conn = get_connection()
        try:
            exists = conn.execute("SELECT 1 FROM daily_performance WHERE id = ?", (performance_id,)).fetchone()
            if not exists:
                raise LookupError("业绩记录不存在")

            conn.execute("DELETE FROM daily_performance WHERE id = ?", (performance_id,))
            conn.commit()
        finally:
            conn.close()


def get_daily_ranking(report_date: str) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                e.name AS employee_name,
                d.deal_count,
                d.high_intent_count,
                d.private_domain_new,
                d.confidence
            FROM daily_performance d
            JOIN employees e ON e.id = d.employee_id
            WHERE d.report_date = ?
            ORDER BY
                d.deal_count DESC,
                d.high_intent_count DESC,
                d.private_domain_new DESC,
                e.name ASC
            """,
            (report_date,),
        ).fetchall()
    finally:
        conn.close()

    ranking: list[dict[str, Any]] = []
    previous_key: tuple[int, int, int] | None = None
    current_rank = 0
    dense_rank = 0

    for row in rows:
        current_rank += 1
        key = (int(row["deal_count"]), int(row["high_intent_count"]), int(row["private_domain_new"]))
        if key != previous_key:
            dense_rank = current_rank
            previous_key = key

        ranking.append(
            {
                "rank": dense_rank,
                "employee_name": row["employee_name"],
                "deal_count": int(row["deal_count"]),
                "high_intent_count": int(row["high_intent_count"]),
                "private_domain_new": int(row["private_domain_new"]),
                "confidence": float(row["confidence"]),
            }
        )
    return ranking
