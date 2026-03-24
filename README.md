# WatchClaw

Open-source host watchdog for OpenClaw systems.

WatchClaw is the local observation layer: it snapshots host state, writes transparent baselines/state/events to disk, and leaves interpretation / summarization to OpenClaw or another LLM-facing layer.

## Current slices

- listener / port change detection via `ss -ltnup`
- watched-file integrity snapshots with create / delete / hash-change events
- SSH/auth monitoring with journal-first incremental reads and logfile fallback
- append-only JSONL event log plus explicit baseline/state files
- timer-friendly CLI and systemd units for a simple host install story

## Install shape

Requirements:
- Linux host
- Python 3.10+
- `ss` available
- `journalctl` recommended for auth monitoring
- root or equivalent read access for auth logs / journal and listener visibility

Install in editable/dev form:

```bash
cd /path/to/watchclaw
python3 -m pip install -e .
```

Generate a starting config:

```bash
watchclaw init-config \
  --output ./watchclaw.config.json \
  --host-id "$(hostname)" \
  --watch-file /etc/ssh/sshd_config \
  --watch-file /etc/sudoers
```

Or print one without writing:

```bash
watchclaw print-default-config --host-id "$(hostname)"
```

A checked-in sample also exists at `examples/config.sample.json`.

## Minimal config

```json
{
  "host_id": "jc-server",
  "storage": {
    "base_dir": "/var/lib/watchclaw"
  },
  "collection": {
    "listeners": {
      "enabled": true,
      "command": ["ss", "-ltnup"]
    },
    "files": {
      "paths": ["/etc/ssh/sshd_config", "/etc/sudoers"]
    },
    "auth": {
      "enabled": true,
      "journal_command": ["journalctl", "-q", "-o", "json", "--no-pager"],
      "log_paths": ["/var/log/auth.log", "/var/log/secure"]
    }
  },
  "runtime": {
    "mode": "timer"
  }
}
```

Default config path:
- `/etc/watchclaw/config.json`

## CLI

```bash
watchclaw status --config ./watchclaw.config.json
watchclaw run-once --config ./watchclaw.config.json
watchclaw print-default-config --host-id jc-server
watchclaw init-config --output ./watchclaw.config.json
```

`watchclaw status` prints the resolved runtime config summary as JSON.

## Local state layout

State is written under `storage.base_dir`:

```text
<base_dir>/
  state.json
  events.jsonl
  baselines/
    listeners.json
    files.json
```

`state.json` persists the last auth cursor / logfile offset so SSH/auth reads stay incremental across runs.

## Event types currently emitted

Listeners:
- `new_listener`
- `listener_removed`

Files:
- `watched_file_created`
- `watched_file_deleted`
- `sensitive_file_hash_changed`

SSH/auth:
- `ssh_login_success`
- `ssh_invalid_user`
- `ssh_failed_login_burst`

## systemd

Real timer-based units live in `systemd/`:
- `watchclaw.service` — one-shot scan using `watchclaw run-once --config /etc/watchclaw/config.json`
- `watchclaw.timer` — runs every 5 minutes, persistent across reboots

Typical install:

```bash
sudo install -d /etc/watchclaw /var/lib/watchclaw
sudo install -m 0644 examples/config.sample.json /etc/watchclaw/config.json
sudo install -m 0644 systemd/watchclaw.service /etc/systemd/system/watchclaw.service
sudo install -m 0644 systemd/watchclaw.timer /etc/systemd/system/watchclaw.timer
sudo systemctl daemon-reload
sudo systemctl enable --now watchclaw.timer
sudo systemctl start watchclaw.service
```

Adjust `/etc/watchclaw/config.json` before enabling if you want a different `host_id`, `base_dir`, or watched files.

## Validate the install

```bash
python3 -m unittest discover -s tests
watchclaw status --config /etc/watchclaw/config.json
sudo watchclaw run-once --config /etc/watchclaw/config.json
sudo systemctl status watchclaw.timer watchclaw.service
sudo journalctl -u watchclaw.service -n 50 --no-pager
```

## Notes

- This project is intentionally local-first and inspectable.
- WatchClaw is not trying to be a SIEM.
- OpenClaw remains the interpretation / response layer, not the source of truth for detection.
