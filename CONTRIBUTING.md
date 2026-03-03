# Contributing

Thanks for your interest in improving FlowForge Local.

## Development setup

```bash
cd /Users/kyleparker/Documents/project\ 3
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --port 8017
```

## Contribution guidelines

- Keep changes focused and scoped to a clear user problem.
- Maintain local-first behavior; avoid cloud dependencies unless explicitly optional.
- Add/update docs for new API endpoints, rule fields, or actions.
- Preserve undo and dry-run semantics for destructive operations.
- Ensure backend files compile before opening a PR.

## Pre-PR checklist

- Run: `python3 -m py_compile backend/app/*.py`
- Verify at least one end-to-end rule run in the UI
- Update README/docs if behavior changed
