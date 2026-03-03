from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

from . import repository
from .engine import AutomationEngine


class SchedulerService:
    def __init__(self, engine: AutomationEngine) -> None:
        self._engine = engine
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._tick()
            self._stop.wait(20)

    def _tick(self) -> None:
        now = datetime.now()
        for rule in repository.list_rules():
            if not rule.get("enabled"):
                continue
            schedule = rule.get("schedule", {})
            if not schedule or not schedule.get("enabled"):
                continue

            interval_minutes = max(1, int(schedule.get("interval_minutes", 60)))
            only_weekdays = bool(schedule.get("weekdays_only", False))
            if only_weekdays and now.weekday() > 4:
                continue

            last_run = repository.get_scheduler_last_run(rule["id"])
            if last_run:
                last_dt = datetime.fromisoformat(last_run.replace("Z", ""))
                if now - last_dt < timedelta(minutes=interval_minutes):
                    continue

            self._engine.run_scheduled_rule(rule, dry_run=bool(schedule.get("dry_run", False)))
            repository.set_scheduler_last_run(rule["id"])
