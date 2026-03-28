# WatchClaw

Open-source host watchdog for OpenClaw systems.

WatchClaw is the local observation layer: it snapshots host state, writes transparent baselines/state/events to disk, and leaves interpretation / summarization to OpenClaw or another LLM-facing layer.

## Current slices

- listener / port change detection via `ss -ltnup`
- watched-file integrity snapshots with create / delete / hash-change events
- SSH/auth monitoring with journal-first incremental reads and logfile fallback
- append-only JSONL event log plus explicit baseline/state files
- append-only JSONL action log for WatchClaw side effects (baseline writes, event appends, state writes) with hash chaining for local auditability
- Telegram delivery-preparation flow with durable per-event state so notification-worthy events are not resent indefinitely
- timer-friendly CLI and systemd units for a simple host install story

## Install shape

System requirements:
- Linux host with `systemd`
- Python 3.10+
- `python3 -m venv` available
- `pip3` available inside the virtual environment
- `ss` available (`iproute2` on most distros)
- root runtime/install access for auth logs / journal and full listener visibility
- `journalctl` recommended for auth monitoring; without it, logfile fallback is used

Recommended install from a source checkout:

```bash
git clone <repo-url>
cd watchclaw
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
pip3 install .
sudo bash scripts/install.sh \
  --venv "$(pwd)/.venv" \
  --host-id "$(hostname)" \
  --watch-file /etc/ssh/sshd_config \
  --watch-file /etc/sudoers
```

What the installer does, explicitly:
- validates the host prerequisites
- uses the already-prepared virtual environment you pass with `--venv` (or `./.venv` by default)
- writes or preserves `/etc/watchclaw/config.json`
- creates `/var/lib/watchclaw`
- renders `watchclaw.service` with the real venv entrypoint and chosen config path
- installs `watchclaw.timer`
- runs one `watchclaw run-once`
- enables and starts the timer

If you want to inspect or reproduce the steps manually, read `scripts/install.sh` and `docs/INSTALLATION.md`.

For local development only, editable install still works:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
pip3 install -e .
```

A checked-in sample config also exists at `examples/config.sample.json`.

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
      "command": ["ss", "-ltnup"],
      "ignore_process_names": ["systemd-resolved"],
      "ignore_local_ports": [5353]
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
watchclaw render-telegram --event-file /var/lib/watchclaw/events.jsonl
watchclaw prepare-telegram-delivery --config /etc/watchclaw/config.json
watchclaw ack-telegram-delivery --config /etc/watchclaw/config.json --batch-id <batch-id> --status sent
```

`watchclaw status` prints the resolved runtime config summary as JSON.

`watchclaw inspect` verifies the local `events.jsonl` and `actions.jsonl` hash chains, summarizes the last `--tail` records from each log, and flags obvious local-file problems such as hash mismatches, broken chain links, blank-line gaps, and interrupted trailing writes.

`watchclaw render-telegram` renders one event or a whole JSONL file of events into Telegram-ready payloads without sending them. This is the UX/searchable-journal layer: WatchClaw keeps disk-first traceability, while downstream delivery layers can consume preformatted, human-facing messages.

`watchclaw prepare-telegram-delivery` is the local bridge from stored events to outbound notifications: it selects unsent default-worthy events, renders Telegram payloads, and persists delivery state in `delivery-state.json` so the same event is not prepared forever.

`watchclaw ack-telegram-delivery` is the thin post-transport step: after OpenClaw or another sender actually sends the prepared payloads, it marks the batch `sent` or `failed` locally.

## Local state layout

State is written under `storage.base_dir`:

```text
<base_dir>/
  state.json
  events.jsonl
  actions.jsonl
  delivery-state.json
  deliveries.jsonl
  baselines/
    listeners.json
    files.json
```

`events.jsonl` and `actions.jsonl` are append-only logs. `actions.jsonl` records WatchClaw's own side effects and links each record to the previous one with a hash chain for local auditability. This improves tamper-evidence direction, but it is not a claim of full immutability or remote attestation.

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

Timer-based units live in `systemd/`:
- `watchclaw.service` — template for a one-shot scan using `watchclaw run-once --config ...`
- `watchclaw.timer` — runs every 5 minutes, persistent across reboots

`scripts/install.sh` renders the service with the actual installed `watchclaw` binary path and your chosen config path, then installs both units into `/etc/systemd/system/`.

If you install manually, render `systemd/watchclaw.service` by replacing:
- `@WATCHCLAW_BIN@` with the real `watchclaw` executable path
- `@WATCHCLAW_CONFIG@` with the real config path

## Validate the install

```bash
python3 -m unittest discover -s tests
bash -n scripts/install.sh
.venv/bin/watchclaw status --config /etc/watchclaw/config.json
sudo .venv/bin/watchclaw run-once --config /etc/watchclaw/config.json
sudo systemctl status watchclaw.timer watchclaw.service
sudo journalctl -u watchclaw.service -n 50 --no-pager
```

## Notes

- This project is intentionally local-first and inspectable.
- WatchClaw is not trying to be a SIEM.
- OpenClaw remains the interpretation / response layer, not the source of truth for detection.
