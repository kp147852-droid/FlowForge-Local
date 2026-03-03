from __future__ import annotations

import csv
import fnmatch
import hashlib
import json
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter

from . import repository


class AutomationEngine:
    def process_file_for_rule(
        self,
        rule: dict,
        file_path: str,
        dry_run: bool = False,
        trigger_depth: int = 0,
    ) -> int:
        path = Path(file_path).expanduser().resolve()
        if not path.exists() or path.is_dir():
            raise ValueError(f"Path does not exist or is a directory: {file_path}")

        if not fnmatch.fnmatch(path.name, rule["pattern"]):
            raise ValueError(f"File {path.name} does not match pattern {rule['pattern']}")

        if not self._matches_conditions(rule, path):
            raise ValueError("File does not match rule conditions")

        fingerprint = self._fingerprint(path)
        dedupe = bool(rule.get("conditions", {}).get("dedupe", True))
        if dedupe and repository.is_duplicate(rule["id"], fingerprint):
            raise ValueError("Duplicate file fingerprint; skipping")

        retries = max(1, int(rule.get("action_config", {}).get("max_retries", 1)))
        backoff_seconds = max(0, int(rule.get("action_config", {}).get("backoff_seconds", 1)))

        job_id = repository.create_job(
            rule_id=rule["id"],
            file_path=str(path),
            status="queued",
            dry_run=dry_run,
            attempt_count=1,
        )
        repository.start_job(job_id)
        repository.add_job_log(job_id, "info", f"Job started (dry_run={dry_run})")

        last_error = None
        for attempt in range(1, retries + 1):
            try:
                repository.add_job_log(job_id, "info", f"Attempt {attempt}/{retries}")
                output, undo = self._run_action(rule, path, dry_run=dry_run)
                repository.complete_job(job_id, output, undo=undo)
                repository.add_job_log(job_id, "info", "Job succeeded")
                if dedupe:
                    repository.mark_processed_file(rule["id"], fingerprint)

                if not dry_run and trigger_depth < 3:
                    self._trigger_downstream_rules(rule, path, trigger_depth)
                self._run_integrations(rule, job_id, "success", output)
                return job_id
            except Exception as exc:
                last_error = str(exc)
                repository.add_job_log(job_id, "error", f"Attempt {attempt} failed: {last_error}")
                if attempt < retries:
                    time.sleep(backoff_seconds)

        repository.fail_job(job_id, last_error or "Unknown failure")
        self._quarantine_on_failure(rule, path)
        self._run_integrations(rule, job_id, "failed", last_error or "Unknown failure")
        return job_id

    def run_scheduled_rule(self, rule: dict, dry_run: bool = False) -> list[int]:
        source_dir = Path(rule["source_dir"]).expanduser().resolve()
        if not source_dir.exists() or not source_dir.is_dir():
            return []

        job_ids: list[int] = []
        for path in source_dir.iterdir():
            if path.is_dir():
                continue
            try:
                job_id = self.process_file_for_rule(rule, str(path), dry_run=dry_run)
                job_ids.append(job_id)
            except Exception:
                continue
        return job_ids

    def undo_job(self, job: dict[str, Any]) -> str:
        undo = job.get("undo")
        if not undo:
            raise ValueError("No undo payload stored for this job")

        operation = undo.get("operation")
        if operation == "move":
            src = Path(undo["to"])
            dest = Path(undo["from"])
            if src.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                return f"Moved back to {dest}"
            raise ValueError("Undo source path no longer exists")

        if operation == "rename":
            src = Path(undo["to"])
            dest = Path(undo["from"])
            if src.exists():
                src.rename(dest)
                return f"Renamed back to {dest.name}"
            raise ValueError("Undo source path no longer exists")

        if operation == "copy":
            copied_path = Path(undo["to"])
            if copied_path.exists():
                copied_path.unlink()
                return f"Removed copied file {copied_path.name}"
            raise ValueError("Copied file already missing")

        raise ValueError(f"Undo operation not supported: {operation}")

    def _matches_conditions(self, rule: dict, path: Path) -> bool:
        conditions = rule.get("conditions", {})
        name = path.name

        contains = str(conditions.get("filename_contains", "")).strip()
        excludes = str(conditions.get("filename_excludes", "")).strip()
        if contains and contains not in name:
            return False
        if excludes and excludes in name:
            return False

        min_size_kb = float(conditions.get("min_size_kb", 0) or 0)
        max_size_kb = float(conditions.get("max_size_kb", 0) or 0)
        size_kb = path.stat().st_size / 1024
        if min_size_kb and size_kb < min_size_kb:
            return False
        if max_size_kb and size_kb > max_size_kb:
            return False

        allowed_extensions = conditions.get("allowed_extensions", [])
        if allowed_extensions:
            exts = {str(ext).lower().lstrip(".") for ext in allowed_extensions}
            if path.suffix.lower().lstrip(".") not in exts:
                return False

        allowed_weekdays = conditions.get("allowed_weekdays", [])
        if allowed_weekdays:
            today = datetime.now().strftime("%a").lower()[:3]
            normalized = {str(day).lower()[:3] for day in allowed_weekdays}
            if today not in normalized:
                return False

        start_h = int(conditions.get("allowed_hour_start", 0) or 0)
        end_h = int(conditions.get("allowed_hour_end", 23) or 23)
        now_h = datetime.now().hour
        if start_h <= end_h:
            if now_h < start_h or now_h > end_h:
                return False
        else:
            if not (now_h >= start_h or now_h <= end_h):
                return False

        return True

    def _run_action(self, rule: dict, path: Path, dry_run: bool = False) -> tuple[str, dict[str, Any] | None]:
        action = rule["action"]
        config = rule.get("action_config", {})

        if action == "copy_to_folder":
            target_dir = self._target_dir(config)
            destination = target_dir / path.name
            if dry_run:
                return f"Dry run: would copy to {destination}", {"operation": "copy", "to": str(destination)}
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            return f"Copied to {destination}", {"operation": "copy", "to": str(destination)}

        if action == "move_to_folder":
            target_dir = self._target_dir(config)
            destination = target_dir / path.name
            if dry_run:
                return f"Dry run: would move to {destination}", {"operation": "move", "from": str(path), "to": str(destination)}
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), destination)
            return f"Moved to {destination}", {"operation": "move", "from": str(path), "to": str(destination)}

        if action == "rename_with_timestamp":
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = str(config.get("prefix", ""))
            suffix = str(config.get("suffix", ""))
            destination = path.with_name(f"{prefix}{path.stem}_{stamp}{suffix}{path.suffix}")
            if dry_run:
                return f"Dry run: would rename to {destination.name}", {"operation": "rename", "from": str(path), "to": str(destination)}
            path.rename(destination)
            return f"Renamed to {destination.name}", {"operation": "rename", "from": str(path), "to": str(destination)}

        if action == "summarize_text_file":
            max_lines = int(config.get("max_lines", 8))
            raw_text = path.read_text(encoding="utf-8", errors="ignore")
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            summary = "\n".join(lines[:max_lines]) or "(empty file)"
            out_path = path.with_suffix(path.suffix + ".summary.txt")
            if dry_run:
                return f"Dry run: would write summary to {out_path.name}", None
            out_path.write_text(summary + "\n", encoding="utf-8")
            return f"Summary written to {out_path.name}", None

        if action == "extract_pdf_text":
            out_path = path.with_suffix(".txt")
            if dry_run:
                return f"Dry run: would extract text to {out_path.name}", None
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            out_path.write_text("\n\n".join(pages), encoding="utf-8")
            return f"Extracted PDF text to {out_path}", None

        if action == "merge_pdfs_in_folder":
            source_dir = Path(rule["source_dir"]).expanduser().resolve()
            output_name = str(config.get("output_name", "merged.pdf"))
            out_path = source_dir / output_name
            pdfs = sorted([p for p in source_dir.glob("*.pdf") if p.is_file()])
            if not pdfs:
                raise ValueError("No PDF files found to merge")
            if dry_run:
                return f"Dry run: would merge {len(pdfs)} PDFs into {out_path}", None
            writer = PdfWriter()
            for pdf in pdfs:
                reader = PdfReader(str(pdf))
                for page in reader.pages:
                    writer.add_page(page)
            with out_path.open("wb") as f:
                writer.write(f)
            return f"Merged {len(pdfs)} PDFs into {out_path}", None

        if action == "convert_image":
            out_format = str(config.get("format", "png")).lower()
            out_path = path.with_suffix(f".{out_format}")
            if dry_run:
                return f"Dry run: would convert image to {out_path.name}", None
            subprocess.run(
                ["sips", "-s", "format", out_format, str(path), "--out", str(out_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            return f"Converted image to {out_path}", None

        if action == "compress_image":
            quality = int(config.get("quality", 70))
            out_path = path.with_name(f"{path.stem}.compressed{path.suffix}")
            if dry_run:
                return f"Dry run: would compress image to {out_path.name}", None
            subprocess.run(["sips", "-s", "formatOptions", str(quality), str(path), "--out", str(out_path)], check=True, capture_output=True, text=True)
            return f"Compressed image to {out_path}", None

        if action == "notify_webhook":
            webhook = str(config.get("webhook_url", "")).strip()
            if not webhook:
                raise ValueError("action_config.webhook_url is required")
            payload = json.dumps({"event": "file_processed", "file_path": str(path), "rule": rule["name"]}).encode("utf-8")
            if dry_run:
                return "Dry run: would POST event to webhook", None
            req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=8):
                pass
            return "Webhook notified", None

        if action == "create_email_draft":
            to_email = str(config.get("to_email", "")).strip()
            drafts_dir = Path(config.get("drafts_dir", str(path.parent))).expanduser().resolve()
            if not to_email:
                raise ValueError("action_config.to_email is required")
            draft_path = drafts_dir / f"draft_{path.stem}.txt"
            content = f"To: {to_email}\nSubject: Processed file {path.name}\n\nFile processed at {datetime.now().isoformat()}\nPath: {path}\n"
            if dry_run:
                return f"Dry run: would create draft at {draft_path}", None
            drafts_dir.mkdir(parents=True, exist_ok=True)
            draft_path.write_text(content, encoding="utf-8")
            return f"Email draft created at {draft_path}", None

        raise ValueError(f"Unknown action: {action}")

    def _target_dir(self, config: dict[str, Any]) -> Path:
        target_raw = str(config.get("target_dir", "")).strip()
        if not target_raw:
            raise ValueError("action_config.target_dir is required")
        return Path(target_raw).expanduser().resolve()

    def _fingerprint(self, path: Path) -> str:
        stat = path.stat()
        base = f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def _trigger_downstream_rules(self, rule: dict, path: Path, trigger_depth: int) -> None:
        downstream_rule_ids = rule.get("schedule", {}).get("downstream_rule_ids", [])
        if not downstream_rule_ids:
            return

        all_rules = {item["id"]: item for item in repository.list_rules() if item.get("enabled")}
        for rule_id in downstream_rule_ids:
            next_rule = all_rules.get(int(rule_id))
            if not next_rule:
                continue
            try:
                self.process_file_for_rule(next_rule, str(path), dry_run=False, trigger_depth=trigger_depth + 1)
            except Exception:
                continue

    def _quarantine_on_failure(self, rule: dict, path: Path) -> None:
        quarantine_raw = str(rule.get("action_config", {}).get("quarantine_dir", "")).strip()
        if not quarantine_raw or not path.exists():
            return

        quarantine_dir = Path(quarantine_raw).expanduser().resolve()
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        destination = quarantine_dir / path.name
        try:
            shutil.copy2(path, destination)
        except Exception:
            pass

    def _run_integrations(self, rule: dict, job_id: int, status: str, message: str) -> None:
        integrations = rule.get("integrations", {})

        webhook = str(integrations.get("notify_webhook", "")).strip()
        if webhook:
            payload = json.dumps(
                {
                    "job_id": job_id,
                    "status": status,
                    "message": message,
                    "rule": rule["name"],
                }
            ).encode("utf-8")
            try:
                req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=8):
                    pass
            except Exception:
                pass

        csv_path = str(integrations.get("append_csv", "")).strip()
        if csv_path:
            target = Path(csv_path).expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            is_new = not target.exists()
            with target.open("a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                if is_new:
                    writer.writerow(["timestamp", "job_id", "status", "rule", "message"])
                writer.writerow([datetime.now().isoformat(), job_id, status, rule["name"], message])
