from __future__ import annotations

import json
from typing import Any

from .db import get_connection


def create_rule(payload: dict[str, Any]) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO rules (
                name, source_dir, pattern, action,
                action_config_json, conditions_json, schedule_json, integrations_json,
                enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["name"],
                payload["source_dir"],
                payload["pattern"],
                payload["action"],
                json.dumps(payload.get("action_config", {})),
                json.dumps(payload.get("conditions", {})),
                json.dumps(payload.get("schedule", {})),
                json.dumps(payload.get("integrations", {})),
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


def create_job(
    rule_id: int,
    file_path: str,
    status: str = "queued",
    dry_run: bool = False,
    attempt_count: int = 1,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs (rule_id, file_path, status, dry_run, attempt_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (rule_id, file_path, status, 1 if dry_run else 0, attempt_count),
        )
        return int(cur.lastrowid)


def start_job(job_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE jobs SET status = 'running', started_at = CURRENT_TIMESTAMP WHERE id = ?",
            (job_id,),
        )


def complete_job(job_id: int, output: str | None, undo: dict[str, Any] | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'success', output = ?, undo_json = ?, finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (output, json.dumps(undo) if undo else None, job_id),
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


def get_job(job_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    if result.get("undo_json"):
        result["undo"] = json.loads(result["undo_json"])
    else:
        result["undo"] = None
    return result


def list_jobs(limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_job_log(job_id: int, level: str, message: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO job_logs (job_id, level, message) VALUES (?, ?, ?)",
            (job_id, level, message),
        )


def list_job_logs(job_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM job_logs WHERE job_id = ? ORDER BY id ASC",
            (job_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def mark_processed_file(rule_id: int, fingerprint: str) -> bool:
    with get_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO processed_files (rule_id, file_fingerprint) VALUES (?, ?)",
                (rule_id, fingerprint),
            )
            return True
        except Exception:
            return False


def is_duplicate(rule_id: int, fingerprint: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM processed_files WHERE rule_id = ? AND file_fingerprint = ?",
            (rule_id, fingerprint),
        ).fetchone()
    return row is not None


def get_scheduler_last_run(rule_id: int) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT last_run_at FROM scheduler_state WHERE rule_id = ?",
            (rule_id,),
        ).fetchone()
    return row[0] if row else None


def set_scheduler_last_run(rule_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO scheduler_state (rule_id, last_run_at)
            VALUES (?, CURRENT_TIMESTAMP)
            ON CONFLICT(rule_id) DO UPDATE SET last_run_at = CURRENT_TIMESTAMP
            """,
            (rule_id,),
        )


def job_metrics() -> dict[str, Any]:
    with get_connection() as conn:
        totals = conn.execute(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success,
              SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
              SUM(CASE WHEN dry_run = 1 THEN 1 ELSE 0 END) AS dry_runs
            FROM jobs
            """
        ).fetchone()
        by_rule = conn.execute(
            """
            SELECT rule_id,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
            FROM jobs
            GROUP BY rule_id
            ORDER BY total DESC
            """
        ).fetchall()

    return {
        "total": int(totals["total"] or 0),
        "success": int(totals["success"] or 0),
        "failed": int(totals["failed"] or 0),
        "dry_runs": int(totals["dry_runs"] or 0),
        "by_rule": [dict(row) for row in by_rule],
    }


def _row_to_rule(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "source_dir": row["source_dir"],
        "pattern": row["pattern"],
        "action": row["action"],
        "action_config": json.loads(row["action_config_json"] or "{}"),
        "conditions": json.loads(row["conditions_json"] or "{}"),
        "schedule": json.loads(row["schedule_json"] or "{}"),
        "integrations": json.loads(row["integrations_json"] or "{}"),
        "enabled": bool(row["enabled"]),
        "created_at": row["created_at"],
    }
