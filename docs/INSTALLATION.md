# Installation

## Goal

Get WatchClaw onto an existing Linux host in a way that is easy to inspect, easy to recover, and aligned with the current timer-based MVP.

## Assumptions

- OpenClaw already exists separately; WatchClaw does not replace it.
- WatchClaw runs locally and writes its own state.
- A systemd timer is the default runtime model.
- Root is the practical runtime user for the current auth/log/listener slices.

## Paths

- config: `/etc/watchclaw/config.json`
- state root: `/var/lib/watchclaw`
- units:
  - `/etc/systemd/system/watchclaw.service`
  - `/etc/systemd/system/watchclaw.timer`

## Recommended flow

1. Install the package:

   ```bash
   python3 -m pip install -e .
   ```

2. Generate or copy a config:

   ```bash
   sudo install -d /etc/watchclaw
   watchclaw print-default-config --host-id "$(hostname)" > ./watchclaw.config.json
   sudo install -m 0644 ./watchclaw.config.json /etc/watchclaw/config.json
   ```

   Or start from the sample file:

   ```bash
   sudo install -m 0644 examples/config.sample.json /etc/watchclaw/config.json
   ```

3. Edit watched files and host identity as needed.

4. Create the state directory:

   ```bash
   sudo install -d /var/lib/watchclaw
   ```

5. Install systemd units:

   ```bash
   sudo install -m 0644 systemd/watchclaw.service /etc/systemd/system/watchclaw.service
   sudo install -m 0644 systemd/watchclaw.timer /etc/systemd/system/watchclaw.timer
   sudo systemctl daemon-reload
   ```

6. Dry-run one scan:

   ```bash
   sudo watchclaw run-once --config /etc/watchclaw/config.json
   ```

7. Enable the timer:

   ```bash
   sudo systemctl enable --now watchclaw.timer
   ```

## What success looks like

- `watchclaw status --config /etc/watchclaw/config.json` returns JSON with the expected paths and flags.
- `/var/lib/watchclaw/state.json` exists after the first run.
- `/var/lib/watchclaw/events.jsonl` exists if drift or auth signals were observed.
- `/var/lib/watchclaw/baselines/` contains listener and/or file baselines depending on enabled slices.
- `systemctl status watchclaw.timer` shows the timer armed.

## Operational notes

- First run establishes baselines, so some change events depend on a second run.
- SSH/auth collection prefers `journalctl` and falls back to `/var/log/auth.log` or `/var/log/secure`.
- The event log is append-only JSONL on purpose: read it directly before adding more abstraction.

## Uninstall / rollback

Stop and disable the timer:

```bash
sudo systemctl disable --now watchclaw.timer
sudo systemctl stop watchclaw.service
```

Remove units if desired:

```bash
sudo rm -f /etc/systemd/system/watchclaw.service /etc/systemd/system/watchclaw.timer
sudo systemctl daemon-reload
```

Config and state can be preserved for forensic review or deleted manually later.
