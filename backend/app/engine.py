from __future__ import annotations

import fnmatch
import shutil
from datetime import datetime
from pathlib import Path

from . import repository


class AutomationEngine:
    def process_file_for_rule(self, rule: dict, file_path: str) -> int:
        path = Path(file_path)
        if not path.exists() or path.is_dir():
            raise ValueError(f"Path does not exist or is a directory: {file_path}")

        if not fnmatch.fnmatch(path.name, rule["pattern"]):
            raise ValueError(f"File {path.name} does not match pattern {rule['pattern']}")

        job_id = repository.create_job(rule_id=rule["id"], file_path=str(path), status="queued")
        repository.start_job(job_id)
        try:
            output = self._run_action(rule, path)
            repository.complete_job(job_id, output)
        except Exception as exc:
            repository.fail_job(job_id, str(exc))
        return job_id

    def _run_action(self, rule: dict, path: Path) -> str:
        action = rule["action"]
        config = rule.get("action_config", {})

        if action == "copy_to_folder":
            target_raw = str(config.get("target_dir", "")).strip()
            if not target_raw:
                raise ValueError("action_config.target_dir is required")
            target_dir = Path(target_raw).expanduser().resolve()
            target_dir.mkdir(parents=True, exist_ok=True)
            destination = target_dir / path.name
            shutil.copy2(path, destination)
            return f"Copied to {destination}"

        if action == "move_to_folder":
            target_raw = str(config.get("target_dir", "")).strip()
            if not target_raw:
                raise ValueError("action_config.target_dir is required")
            target_dir = Path(target_raw).expanduser().resolve()
            target_dir.mkdir(parents=True, exist_ok=True)
            destination = target_dir / path.name
            shutil.move(str(path), destination)
            return f"Moved to {destination}"

        if action == "rename_with_timestamp":
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = config.get("prefix", "")
            suffix = config.get("suffix", "")
            destination = path.with_name(f"{prefix}{path.stem}_{stamp}{suffix}{path.suffix}")
            path.rename(destination)
            return f"Renamed to {destination.name}"

        if action == "summarize_text_file":
            max_lines = int(config.get("max_lines", 8))
            raw_text = path.read_text(encoding="utf-8", errors="ignore")
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            summary = "\n".join(lines[:max_lines]) or "(empty file)"
            out_path = path.with_suffix(path.suffix + ".summary.txt")
            out_path.write_text(summary + "\n", encoding="utf-8")
            return f"Summary written to {out_path.name}"

        raise ValueError(f"Unknown action: {action}")
