"""SQLite 存储：账本历史 + 自动去重。"""
from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from accounting_agent.models import Transaction


class LedgerDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    date       TEXT NOT NULL,
                    time       TEXT,
                    amount     REAL NOT NULL,
                    type       TEXT NOT NULL CHECK (type IN ('income','expense')),
                    category   TEXT NOT NULL DEFAULT '其他',
                    merchant   TEXT NOT NULL DEFAULT '',
                    note       TEXT,
                    raw_text   TEXT,
                    created_at TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL UNIQUE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON transactions(date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON transactions(type)")

    # ---------- 写入 ----------
    def insert_many(self, txs: list[Transaction]) -> tuple[list[Transaction], list[Transaction]]:
        """返回 (已入库, 重复丢弃)。dedupe_key 唯一约束自动去重。"""
        inserted, duplicates = [], []
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as conn:
            for tx in txs:
                key = self._dedupe_key(tx)
                try:
                    conn.execute(
                        "INSERT INTO transactions (date, time, amount, type, category, merchant, note, raw_text, created_at, dedupe_key)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (tx.date, tx.time, tx.amount, tx.type, tx.category,
                         tx.merchant, tx.note, tx.raw_text, now, key),
                    )
                    inserted.append(tx)
                except sqlite3.IntegrityError:
                    duplicates.append(tx)
        return inserted, duplicates

    @staticmethod
    def _dedupe_key(tx: Transaction) -> str:
        return "|".join([tx.date, tx.time or "", f"{tx.amount:.2f}", tx.merchant])

    # ---------- 查询 ----------
    def all(self, limit: int | None = None) -> list[Transaction]:
        with self._conn() as conn:
            cur = conn.execute("SELECT * FROM transactions ORDER BY date DESC, time DESC"
                               + (f" LIMIT {int(limit)}" if limit else ""))
            return [self._row_to_tx(r) for r in cur.fetchall()]

    def since(self, start_date: str) -> list[Transaction]:
        with self._conn() as conn:
            cur = conn.execute("SELECT * FROM transactions WHERE date >= ? ORDER BY date ASC, time ASC", (start_date,))
            return [self._row_to_tx(r) for r in cur.fetchall()]

    def count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]

    @staticmethod
    def _row_to_tx(r: sqlite3.Row) -> Transaction:
        return Transaction(
            date=r["date"], time=r["time"], amount=r["amount"], type=r["type"],
            category=r["category"], merchant=r["merchant"], note=r["note"], raw_text=r["raw_text"],
        )

    # ---------- 导出 ----------
    def export_csv(self, csv_path: str) -> str:
        Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["日期", "时间", "金额", "收支", "类别", "商户", "备注"])
            for tx in self.all():
                writer.writerow([tx.date, tx.time or "", tx.amount, tx.type, tx.category,
                                 tx.merchant, tx.note or ""])
        return csv_path
