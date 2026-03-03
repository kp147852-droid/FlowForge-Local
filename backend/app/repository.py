from __future__ import annotations

import json
from typing import Any

from .db import get_connection


def create_rule(payload: dict[str, Any]) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO rules (name, source_dir, pattern, action, action_config_json, enabled)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload["name"],
                payload["source_dir"],
                payload["pattern"],
                payload["action"],
                json.dumps(payload.get("action_config", {})),
                1 if payload.get("enabled", True) else 0,
            ),
        )
        return int(cur.lastrowid)


def list_rules() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM rules ORDER BY id DESC").fetchall()
    return [_row_to_rule(row) for row in rows]


def get_rule(rule_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
    return _row_to_rule(row) if row else None


def set_rule_enabled(rule_id: int, enabled: bool) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE rules SET enabled = ? WHERE id = ?",
            (1 if enabled else 0, rule_id),
        )
    return cur.rowcount > 0


def create_job(rule_id: int, file_path: str, status: str = "queued") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs (rule_id, file_path, status)
            VALUES (?, ?, ?)
            """,
            (rule_id, file_path, status),
        )
        return int(cur.lastrowid)


def start_job(job_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE jobs SET status = 'running', started_at = CURRENT_TIMESTAMP WHERE id = ?",
            (job_id,),
        )


def complete_job(job_id: int, output: str | None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'success', output = ?, finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (output, job_id),
        )


def fail_job(job_id: int, error: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'failed', error = ?, finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (error, job_id),
        )


def list_jobs(limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _row_to_rule(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "source_dir": row["source_dir"],
        "pattern": row["pattern"],
        "action": row["action"],
        "action_config": json.loads(row["action_config_json"] or "{}"),
        "enabled": bool(row["enabled"]),
        "created_at": row["created_at"],
    }
