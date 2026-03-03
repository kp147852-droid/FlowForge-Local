# Case Study: FlowForge Local

## Problem
Knowledge workers and small teams spend significant time moving, renaming, and extracting information from files.
Manual handling increases operational latency and creates inconsistent audit trails.

## Approach
Built a local-first automation platform with:
- event-driven triggers (folder watcher)
- scheduled execution
- configurable rules (conditions + actions)
- reliability controls (retry, backoff, quarantine, dry-run, undo)
- observable outcomes (job logs + metrics)

## Solution design
- FastAPI API layer for rule/job orchestration
- SQLite persistence for rules, jobs, logs, scheduler state, and dedupe fingerprints
- Automation engine to execute rule actions safely
- Browser UI for rule authoring, manual runs, templates, and metrics

## Impact (project-level)
- Demonstrates translation of ambiguous business workflows into deterministic process logic.
- Demonstrates production-oriented controls and observability patterns.
- Demonstrates cross-functional product thinking across backend, frontend, and UX.

## Relevance to roles
- Business Analyst: requirements decomposition, workflow mapping, process control design.
- Data Scientist: structured telemetry, reproducibility, and data extraction pathways.
- AI Engineer/Applied AI: automation architecture and integration-ready pipelines.

## Next evolution
- add queue-backed execution
- add cloud source connectors (Drive/Dropbox)
- add OCR + entity extraction for invoice intelligence
