# WatchClaw

Open-source host watchdog for OpenClaw systems.

## Goal

Provide a portable security-watchdog layer for machines that already run OpenClaw.

Initial focus:
- SSH login monitoring
- sensitive file integrity checks
- listener/port change detection
- alert delivery through OpenClaw-compatible flows
- installable on an existing Linux host with OpenClaw already running

## Status

First runnable listener slice is in place.

## MVP usage

```bash
PYTHONPATH=src python3 -m watchclaw.cli status
PYTHONPATH=src python3 -m watchclaw.cli run-once --config /etc/watchclaw/config.json
```

State written under `storage.base_dir`:

- `state.json`
- `events.jsonl`
- `baselines/listeners.json`
