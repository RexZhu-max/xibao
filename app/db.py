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
