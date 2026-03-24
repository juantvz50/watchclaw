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

Runnable listener, watched-file, and SSH auth-monitoring slices are in place.

## MVP usage

```bash
PYTHONPATH=src python3 -m watchclaw.cli status
PYTHONPATH=src python3 -m watchclaw.cli run-once --config /etc/watchclaw/config.json
```

State written under `storage.base_dir`:

- `state.json`
- `events.jsonl`
- `baselines/listeners.json`
- `baselines/files.json`

`state.json` now also persists the last auth cursor / logfile offset so SSH/auth reads stay incremental across runs.

Minimal file-integrity config:

```json
{
  "collection": {
    "files": {
      "paths": ["/etc/ssh/sshd_config", "/etc/sudoers"]
    }
  }
}
```

Minimal auth config override:

```json
{
  "collection": {
    "auth": {
      "enabled": true,
      "journal_command": ["journalctl", "-q", "-o", "json", "--no-pager"],
      "log_paths": ["/var/log/auth.log", "/var/log/secure"]
    }
  }
}
```

Current SSH/auth events:
- `ssh_login_success`
- `ssh_invalid_user`
- `ssh_failed_login_burst`
