# Desktop Packaging Notes

FlowForge Local is now structured to be packaged with a desktop wrapper.

## Option 1: Tauri shell

- Start backend on app launch (`uvicorn backend.app.main:app --port 8017`)
- Open embedded webview at `http://127.0.0.1:8017`
- Bundle Python runtime or require local Python install

## Option 2: Electron shell

- Spawn backend process from main Electron process
- Wait for health endpoint `/api/health`
- Load BrowserWindow URL `http://127.0.0.1:8017`

## Packaging priorities

- Add app menu for start/stop scheduler and open log folder
- Add local settings file for default folders and startup behavior
- Add signed builds for macOS and Windows
