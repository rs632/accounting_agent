"""Outbox 记录：每次发送给用户的记录（报告路径、时间、图表列表）。"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


class Outbox:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sent_at TEXT NOT NULL,
                    report_path TEXT NOT NULL,
                    charts TEXT,
                    summary TEXT
                )
            """)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def record(self, report_path: str, charts: list[str], summary: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO outbox (sent_at, report_path, charts, summary) VALUES (?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), report_path,
                 ",".join(charts), summary),
            )
            return cur.lastrowid

    def recent(self, limit: int = 10) -> list[sqlite3.Row]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM outbox ORDER BY id DESC LIMIT ?", (limit,))
            return cur.fetchall()
