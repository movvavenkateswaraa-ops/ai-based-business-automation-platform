"""SQLite storage: processed tickets, scored leads and an audit log.

The primary keys (ticket_id / lead_id) make the platform idempotent:
re-running it never processes the same item twice.
"""

import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id    TEXT PRIMARY KEY,
    customer     TEXT,
    subject      TEXT,
    message      TEXT,
    category     TEXT,
    priority     TEXT,
    sentiment    TEXT,
    summary      TEXT,
    reply        TEXT,
    team         TEXT,
    sla_hours    INTEGER,
    escalated    INTEGER,
    engine       TEXT,
    processed_at TEXT
);

CREATE TABLE IF NOT EXISTS leads (
    lead_id      TEXT PRIMARY KEY,
    company      TEXT,
    contact      TEXT,
    email        TEXT,
    employees    TEXT,
    budget       TEXT,
    source       TEXT,
    message      TEXT,
    score        INTEGER,
    tier         TEXT,
    summary      TEXT,
    next_action  TEXT,
    engine       TEXT,
    processed_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    at     TEXT NOT NULL,
    event  TEXT NOT NULL,
    detail TEXT
);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # ---- existence checks ----
    def has_ticket(self, ticket_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone() is not None

    def has_lead(self, lead_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM leads WHERE lead_id = ?", (lead_id,)).fetchone() is not None

    # ---- saving ----
    def _insert(self, table: str, record: dict) -> None:
        columns = ", ".join(record)
        marks = ", ".join("?" for _ in record)
        with self.conn:
            self.conn.execute(f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({marks})", tuple(record.values()))

    def save_ticket(self, record: dict) -> None:
        self._insert("tickets", {**record, "processed_at": now()})

    def save_lead(self, record: dict) -> None:
        self._insert("leads", {**record, "processed_at": now()})

    def log(self, event: str, detail: str = "") -> None:
        with self.conn:
            self.conn.execute("INSERT INTO audit_log (at, event, detail) VALUES (?, ?, ?)", (now(), event, detail))

    # ---- reading ----
    def all_tickets(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM tickets ORDER BY ticket_id")]

    def all_leads(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM leads ORDER BY score DESC, lead_id")]

    def recent_log(self, limit: int = 10) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))]
