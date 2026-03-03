# Local-First Workflow Automator

A local automation app that watches folders and runs file workflows based on rules.

## Features

- Create rules from a browser UI
- Watch local folders for new files
- Actions:
  - copy to folder
  - move to folder
  - rename with timestamp
  - summarize text files
- Persist rules/jobs in local SQLite (`data/automator.db`)
- View execution history

## Run

```bash
cd /Users/kyleparker/Documents/project\ 3
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

## Notes

- Use absolute paths for `source_dir` and manual run file paths.
- If a watched source directory does not exist, watcher registration is skipped until you create it and restart.
