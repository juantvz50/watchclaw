# Installation

## Goal

Get WatchClaw onto an existing Linux host in a way that is easy to inspect, easy to recover, and aligned with the current timer-based MVP.

## Assumptions

- OpenClaw already exists separately; WatchClaw does not replace it.
- WatchClaw runs locally and writes its own state.
- A systemd timer is the default runtime model.
- Root is the practical runtime user for the current auth/log/listener slices.
- Python package installation happens inside a dedicated virtual environment.

## Quick Debian/Ubuntu prerequisites

If the host is missing basic tooling, install the common prerequisites first:

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip iproute2 systemd
```

## System requirements

Required:
- Linux host
- `systemd` + `systemctl`
- Python 3.10+
- `python3 -m venv`
- `pip3` available inside the virtual environment
- `ss` available in PATH
- root install/runtime access

Recommended:
- `journalctl` for journal-first auth monitoring

Notes:
- If `journalctl` is missing, auth collection falls back to `/var/log/auth.log` or `/var/log/secure` when available.
- The checked-in service unit is a template; the install flow renders the real `watchclaw` executable path from your venv.

## Paths

- recommended local venv: `<repo>/.venv`
- config: `/etc/watchclaw/config.json`
- state root: `/var/lib/watchclaw`
- units:
  - `/etc/systemd/system/watchclaw.service`
  - `/etc/systemd/system/watchclaw.timer`

## Recommended flow

From a source checkout:

```bash
git clone <repo-url>
cd watchclaw
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
pip3 install .
sudo bash scripts/install.sh \
  --venv "$(pwd)/.venv" \
  --host-id "$(hostname)"
```

What the installer does:

1. Validates prerequisites (`systemctl`, `install`, `sed`, `ss`, Linux, root).
2. Validates that the requested virtual environment already contains a runnable `watchclaw` install.
3. Writes `/etc/watchclaw/config.json` unless it already exists.
4. Creates `/var/lib/watchclaw`.
5. Renders and installs the systemd units into `/etc/systemd/system/`.
6. Runs one immediate `watchclaw run-once --config /etc/watchclaw/config.json`.
7. Enables and starts `watchclaw.timer`.

Important installer behavior:
- `--venv` is the main contract; if omitted, the installer will try `./.venv` first and `./venv` second
- existing config is preserved by default
- use `--force-config` to regenerate it
- the installer no longer writes into the system Python environment

## Manual equivalent

If you do not want the helper script, these are the same steps in plain commands.

1. Create and populate the venv:

   ```bash
   cd /path/to/watchclaw
   python3 -m venv .venv
   source .venv/bin/activate
   pip3 install -r requirements.txt
   pip3 install .
   ```

2. Generate directories and config:

   ```bash
   sudo install -d /etc/watchclaw /var/lib/watchclaw
   .venv/bin/watchclaw init-config \
     --output ./watchclaw.config.json \
     --force \
     --host-id "$(hostname)" \
     --base-dir /var/lib/watchclaw
   sudo install -m 0644 ./watchclaw.config.json /etc/watchclaw/config.json
   ```

3. Render the service unit with the actual binary path:

   ```bash
   WATCHCLAW_BIN="$(pwd)/.venv/bin/watchclaw"
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
   sudo .venv/bin/watchclaw run-once --config /etc/watchclaw/config.json
   sudo systemctl enable --now watchclaw.timer
   ```

## Upgrade / redeploy an existing host

This step matters after code changes. Updating the git checkout alone does not update the installed package inside the live venv, and it does not rerender the systemd unit.

Supported upgrade flow:

```bash
cd /path/to/watchclaw
sudo bash scripts/upgrade.sh \
  --venv "$(pwd)/.venv" \
  --config /etc/watchclaw/config.json
```

What it does:
1. `git pull --ff-only` unless `--skip-git-pull` is passed.
2. Reinstalls dependencies and `watchclaw` into the same venv.
3. Reruns `scripts/install.sh` with the same venv/config path so the service unit stays aligned with the actual installed binary.
4. Prints `watchclaw status` so you can verify the runtime identity immediately.

Useful validation after an upgrade:

```bash
sudo .venv/bin/watchclaw status --config /etc/watchclaw/config.json
sudo systemctl status watchclaw.timer watchclaw.service
sudo journalctl -u watchclaw.service -n 50 --no-pager
```

Read the `status` JSON instead of guessing. It now reports the package version, installed distribution version, Python executable, module path, rendered systemd `ExecStart`, and declared capabilities.

## What success looks like

- `.venv/bin/watchclaw --help` works.
- `watchclaw status --config /etc/watchclaw/config.json` returns JSON with the expected paths and flags.
- `/var/lib/watchclaw/state.json` exists after the first run.
- `/var/lib/watchclaw/events.jsonl` exists if drift or auth signals were observed.
- `/var/lib/watchclaw/baselines/` contains listener and/or file baselines depending on enabled slices.
- `systemctl status watchclaw.timer` shows the timer armed.

## Operational notes

- First run establishes baselines, so some change events depend on a second run.
- SSH/auth collection prefers `journalctl` and falls back to `/var/log/auth.log` or `/var/log/secure`.
- The event log is append-only JSONL on purpose: read it directly before adding more abstraction.
- Prefer `scripts/upgrade.sh` over ad-hoc `pip3 install .` so the installed package, venv entrypoint, and systemd unit stay aligned.

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
