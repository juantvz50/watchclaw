# Installation

## Goal

Get WatchClaw onto an existing Linux host in a way that is easy to inspect, easy to recover, and aligned with the current timer-based MVP.

## Assumptions

- OpenClaw already exists separately; WatchClaw does not replace it.
- WatchClaw runs locally and writes its own state.
- A systemd timer is the default runtime model.
- Root is the practical runtime user for the current auth/log/listener slices.

## System requirements

Required:
- Linux host
- `systemd` + `systemctl`
- Python 3.10+
- `python3 -m pip`
- `ss` available in PATH
- root install/runtime access

Recommended:
- `journalctl` for journal-first auth monitoring

Notes:
- If `journalctl` is missing, auth collection falls back to `/var/log/auth.log` or `/var/log/secure` when available.
- The checked-in service unit is a template; the install flow must render the real `watchclaw` executable path.

## Paths

- config: `/etc/watchclaw/config.json`
- state root: `/var/lib/watchclaw`
- units:
  - `/etc/systemd/system/watchclaw.service`
  - `/etc/systemd/system/watchclaw.timer`

## Recommended flow

Single command from a source checkout:

```bash
cd /path/to/watchclaw
sudo ./scripts/install.sh \
  --host-id "$(hostname)" \
  --watch-file /etc/ssh/sshd_config \
  --watch-file /etc/sudoers
```

What the installer does:

1. Validate prerequisites (`python3`, `pip`, `systemctl`, `ss`, Linux, root).
2. Install the package from the current checkout:

   ```bash
   python3 -m pip install --prefix /usr/local .
   ```

3. Write `/etc/watchclaw/config.json` unless it already exists.
4. Create `/var/lib/watchclaw`.
5. Render and install the systemd units into `/etc/systemd/system/`.
6. Run one immediate `watchclaw run-once --config /etc/watchclaw/config.json`.
7. Enable and start `watchclaw.timer`.

Important installer behavior:
- existing config is preserved by default
- use `--force-config` to regenerate it
- if your distro blocks system pip writes, you may explicitly opt into `PIP_BREAK_SYSTEM_PACKAGES=1`

## Manual equivalent

If you do not want the helper script, these are the same steps in plain commands.

1. Install the package:

   ```bash
   cd /path/to/watchclaw
   sudo python3 -m pip install --prefix /usr/local .
   ```

2. Generate a config:

   ```bash
   sudo install -d /etc/watchclaw /var/lib/watchclaw
   watchclaw init-config \
     --output ./watchclaw.config.json \
     --force \
     --host-id "$(hostname)" \
     --base-dir /var/lib/watchclaw \
     --watch-file /etc/ssh/sshd_config \
     --watch-file /etc/sudoers
   sudo install -m 0644 ./watchclaw.config.json /etc/watchclaw/config.json
   ```

3. Render the service unit with the actual binary path:

   ```bash
   WATCHCLAW_BIN="$(command -v watchclaw)"
   sed \
     -e "s|@WATCHCLAW_BIN@|$WATCHCLAW_BIN|g" \
     -e "s|@WATCHCLAW_CONFIG@|/etc/watchclaw/config.json|g" \
     systemd/watchclaw.service | sudo tee /etc/systemd/system/watchclaw.service >/dev/null
   sudo install -m 0644 systemd/watchclaw.timer /etc/systemd/system/watchclaw.timer
   sudo chmod 0644 /etc/systemd/system/watchclaw.service /etc/systemd/system/watchclaw.timer
   sudo systemctl daemon-reload
   ```

4. Run first scan and enable the timer:

   ```bash
   sudo watchclaw run-once --config /etc/watchclaw/config.json
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
