from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .engine import AutomationEngine
from . import repository
from .scheduler import SchedulerService
from .schemas import ImportRulesRequest, JobRead, RuleCreate, RuleRead, RuleToggle, RunRequest
from .watcher import WatchService

engine = AutomationEngine()
watcher = WatchService(engine)
scheduler = SchedulerService(engine)

RULE_TEMPLATES: list[dict] = [
    {
        "name": "Invoice Organizer",
        "source_dir": "~/Downloads",
        "pattern": "*.pdf",
        "action": "move_to_folder",
        "action_config": {"target_dir": "~/Documents/Invoices", "max_retries": 2, "backoff_seconds": 1},
        "conditions": {"filename_contains": "invoice", "dedupe": True},
        "schedule": {"enabled": True, "interval_minutes": 60, "weekdays_only": True},
        "integrations": {},
    },
    {
        "name": "Text Summarizer",
        "source_dir": "~/Documents/Notes",
        "pattern": "*.txt",
        "action": "summarize_text_file",
        "action_config": {"max_lines": 10},
        "conditions": {"min_size_kb": 1, "dedupe": True},
        "schedule": {"enabled": False},
        "integrations": {},
    },
    {
        "name": "PDF Extractor",
        "source_dir": "~/Downloads",
        "pattern": "*.pdf",
        "action": "extract_pdf_text",
        "action_config": {},
        "conditions": {"dedupe": True},
        "schedule": {"enabled": False},
        "integrations": {},
    },
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    watcher.start()
    watcher.sync_rules(repository.list_rules())
    scheduler.start()
    try:
        yield
    finally:
        scheduler.stop()
        watcher.stop()


app = FastAPI(title="FlowForge Local", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/templates")
def api_templates() -> list[dict]:
    return RULE_TEMPLATES


@app.get("/api/rules", response_model=list[RuleRead])
def api_list_rules() -> list[dict]:
    return repository.list_rules()


@app.post("/api/rules", response_model=RuleRead)
def api_create_rule(payload: RuleCreate) -> dict:
    rule_id = repository.create_rule(payload.model_dump())
    watcher.sync_rules(repository.list_rules())
    created = repository.get_rule(rule_id)
    if not created:
        raise HTTPException(status_code=500, detail="Rule creation failed")
    return created


@app.post("/api/rules/import")
def api_import_rules(payload: ImportRulesRequest) -> dict[str, int]:
    imported = 0
    for rule in payload.rules:
        repository.create_rule(rule.model_dump())
        imported += 1
    watcher.sync_rules(repository.list_rules())
    return {"imported": imported}


@app.get("/api/rules/export")
def api_export_rules() -> dict[str, list[dict]]:
    return {"rules": repository.list_rules()}


@app.patch("/api/rules/{rule_id}")
def api_toggle_rule(rule_id: int, payload: RuleToggle) -> dict[str, bool]:
    ok = repository.set_rule_enabled(rule_id, payload.enabled)
    if not ok:
        raise HTTPException(status_code=404, detail="Rule not found")
    watcher.sync_rules(repository.list_rules())
    return {"ok": True}


@app.post("/api/rules/{rule_id}/run")
def api_run_rule(rule_id: int, payload: RunRequest) -> dict[str, int]:
    rule = repository.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    try:
        job_id = engine.process_file_for_rule(rule, payload.file_path, dry_run=payload.dry_run)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job_id": job_id}


@app.get("/api/jobs", response_model=list[JobRead])
def api_list_jobs(limit: int = 100) -> list[dict]:
    return repository.list_jobs(limit=limit)


@app.get("/api/jobs/{job_id}/logs")
def api_job_logs(job_id: int) -> list[dict]:
    return repository.list_job_logs(job_id)


@app.post("/api/jobs/{job_id}/undo")
def api_job_undo(job_id: int) -> dict[str, str]:
    job = repository.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        message = engine.undo_job(job)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": message}


@app.get("/api/metrics")
def api_metrics() -> dict:
    return repository.job_metrics()
