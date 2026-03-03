# FlowForge Local

FlowForge Local is a local-first workflow automator that watches folders, applies file rules, and keeps transparent execution history.

## Included features

- File actions: copy, move, timestamp rename, summarize text, extract PDF text, merge PDFs, image convert, image compress
- Rule conditions: file size, filename include/exclude, extension allow-list, weekday and hour window, duplicate detection
- Safe controls: dry-run mode, undo move/rename/copy, quarantine-on-failure
- Scheduling and triggers: interval scheduler, weekdays-only mode, downstream rule chains
- Integrations: webhook notifications and CSV run logs
- Observability: job logs, attempt/retry with backoff, metrics endpoint and UI cards
- Rule templates: preset starter templates
- Rule portability: JSON export/import

## Run

```bash
cd /Users/kyleparker/Documents/project\ 3
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --port 8017
```

Open [http://127.0.0.1:8017](http://127.0.0.1:8017).

## API quick list

- `GET /api/templates`
- `GET /api/rules`
- `POST /api/rules`
- `POST /api/rules/import`
- `GET /api/rules/export`
- `PATCH /api/rules/{rule_id}`
- `POST /api/rules/{rule_id}/run` (`{"file_path": "...", "dry_run": true}`)
- `GET /api/jobs`
- `GET /api/jobs/{job_id}/logs`
- `POST /api/jobs/{job_id}/undo`
- `GET /api/metrics`

## Notes

- Paths should be absolute for predictable behavior.
- Image and PDF actions require the Python packages in `backend/requirements.txt`.
- Scheduler checks rules every 20 seconds and runs those whose interval has elapsed.
