"""SQLite-Datenbank fuer offene Rechnungen und Freigabe-Historie."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL UNIQUE,
    sender TEXT,
    recipient TEXT,
    amount REAL,
    received_at TEXT,
    comment TEXT NOT NULL DEFAULT '',
    pages INTEGER,
    added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    sender TEXT,
    recipient TEXT,
    amount REAL,
    received_at TEXT,
    approver TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    approved_at TEXT NOT NULL,
    archive_path TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            try:
                conn.execute("ALTER TABLE invoices ADD COLUMN pages INTEGER")
            except sqlite3.OperationalError:
                pass

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def scan_insert(self, entries: list[dict]) -> int:
        added = 0
        with self._lock, self._connect() as conn:
            for entry in entries:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO invoices "
                    "(filename, filepath, sender, recipient, amount, received_at, pages, added_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        entry["filename"],
                        entry["filepath"],
                        entry["sender"],
                        entry["recipient"],
                        entry["amount"],
                        entry["received_at"],
                        entry.get("pages"),
                        entry["added_at"],
                    ),
                )
                added += cur.rowcount
                conn.execute(
                    "UPDATE invoices SET pages = ? WHERE filepath = ?",
                    (entry.get("pages"), entry["filepath"]),
                )
            conn.execute(
                "DELETE FROM invoices WHERE filepath NOT IN "
                f"({', '.join('?' for _ in entries) or "''"})",
                [e["filepath"] for e in entries],
            )
        return added

    def list_pending(self) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM invoices ORDER BY received_at DESC, id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_invoice(self, invoice_id: int) -> dict | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM invoices WHERE id = ?", (invoice_id,)
            ).fetchone()
        return dict(row) if row else None

    def set_comment(self, invoice_id: int, comment: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE invoices SET comment = ? WHERE id = ?", (comment, invoice_id)
            )

    def delete_invoice(self, invoice_id: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))

    def update_pages(self, invoice_id: int, pages: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE invoices SET pages = ? WHERE id = ?", (pages, invoice_id)
            )

    def record_approval(self, entry: dict) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO history "
                "(filename, sender, recipient, amount, received_at, approver, comment, "
                " approved_at, archive_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry["filename"],
                    entry["sender"],
                    entry["recipient"],
                    entry["amount"],
                    entry["received_at"],
                    entry["approver"],
                    entry["comment"],
                    entry["approved_at"],
                    entry["archive_path"],
                ),
            )

    def list_history(self) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM history ORDER BY approved_at DESC, id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_history_entry(self, entry_id: int) -> dict | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM history WHERE id = ?", (entry_id,)
            ).fetchone()
        return dict(row) if row else None
