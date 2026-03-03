from __future__ import annotations

import threading
from collections import defaultdict
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .engine import AutomationEngine


class _ChangeHandler(FileSystemEventHandler):
    def __init__(self, service: "WatchService") -> None:
        super().__init__()
        self._service = service

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._service.dispatch_file(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._service.dispatch_file(event.dest_path)


class WatchService:
    def __init__(self, engine: AutomationEngine) -> None:
        self._engine = engine
        self._observer = Observer()
        self._handler = _ChangeHandler(self)
        self._lock = threading.Lock()
        self._rules_by_dir: dict[str, list[dict]] = defaultdict(list)
        self._scheduled_dirs: set[str] = set()

    def start(self) -> None:
        self._observer.start()

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=3)

    def sync_rules(self, rules: list[dict]) -> None:
        with self._lock:
            self._rules_by_dir.clear()
            for rule in rules:
                if not rule["enabled"]:
                    continue
                directory = str(Path(rule["source_dir"]).expanduser().resolve())
                self._rules_by_dir[directory].append(rule)
                if directory not in self._scheduled_dirs and Path(directory).exists():
                    self._observer.schedule(self._handler, directory, recursive=False)
                    self._scheduled_dirs.add(directory)

    def dispatch_file(self, file_path: str) -> None:
        resolved = str(Path(file_path).resolve())
        parent = str(Path(resolved).parent)

        with self._lock:
            rules = list(self._rules_by_dir.get(parent, []))

        for rule in rules:
            try:
                self._engine.process_file_for_rule(rule, resolved)
            except Exception:
                # Job-level failures are captured by engine; ignore watcher-level errors.
                continue
