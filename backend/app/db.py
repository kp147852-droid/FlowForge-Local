from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "automator.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    names = {row[1] for row in rows}
    if column not in names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                source_dir TEXT NOT NULL,
                pattern TEXT NOT NULL,
                action TEXT NOT NULL,
                action_config_json TEXT NOT NULL,
                conditions_json TEXT NOT NULL DEFAULT '{}',
                schedule_json TEXT NOT NULL DEFAULT '{}',
                integrations_json TEXT NOT NULL DEFAULT '{}',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                status TEXT NOT NULL,
                output TEXT,
                error TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 1,
                dry_run INTEGER NOT NULL DEFAULT 0,
                undo_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                started_at TEXT,
                finished_at TEXT,
                FOREIGN KEY(rule_id) REFERENCES rules(id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER NOT NULL,
                file_fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(rule_id, file_fingerprint)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduler_state (
                rule_id INTEGER PRIMARY KEY,
                last_run_at TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            )
            """
        )

        _add_column_if_missing(conn, "rules", "conditions_json", "conditions_json TEXT NOT NULL DEFAULT '{}' ")
        _add_column_if_missing(conn, "rules", "schedule_json", "schedule_json TEXT NOT NULL DEFAULT '{}' ")
        _add_column_if_missing(conn, "rules", "integrations_json", "integrations_json TEXT NOT NULL DEFAULT '{}' ")
        _add_column_if_missing(conn, "jobs", "attempt_count", "attempt_count INTEGER NOT NULL DEFAULT 1")
        _add_column_if_missing(conn, "jobs", "dry_run", "dry_run INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "jobs", "undo_json", "undo_json TEXT")
