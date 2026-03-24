#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_CONFIG_PATH="/etc/watchclaw/config.json"
DEFAULT_STATE_DIR="/var/lib/watchclaw"
DEFAULT_HOST_ID="$(hostname)"
DEFAULT_VENV_PATH="$REPO_ROOT/.venv"
CONFIG_PATH="$DEFAULT_CONFIG_PATH"
STATE_DIR="$DEFAULT_STATE_DIR"
HOST_ID="$DEFAULT_HOST_ID"
FORCE_CONFIG=0
VENV_PATH=""
WATCH_FILES=()

usage() {
  cat <<'EOF'
Usage: sudo ./scripts/install.sh [options]

Minimal installer for a local WatchClaw host setup.
It expects WatchClaw to already be installed into a virtual environment,
then writes a config, creates the state directory, installs systemd units,
runs one scan, and enables the timer.

Recommended flow:
  python3 -m venv .venv
  source .venv/bin/activate
  pip3 install -r requirements.txt
  pip3 install .
  sudo bash scripts/install.sh --venv /absolute/path/to/.venv

Options:
  --venv PATH           Virtual environment that already has WatchClaw installed.
                        If omitted, the installer will use ./venv or ./.venv when run
                        from the repository root. Default preferred path: ./.venv
  --config PATH         Config path to write (default: /etc/watchclaw/config.json)
  --state-dir PATH      State directory (default: /var/lib/watchclaw)
  --host-id ID          Host identifier for generated config (default: hostname)
  --watch-file PATH     Add a watched file path (repeatable)
  --force-config        Overwrite an existing config file
  --help                Show this help
EOF
}

log() {
  printf '==> %s\n' "$*"
}

warn() {
  printf 'warning: %s\n' "$*" >&2
}

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

resolve_venv_path() {
  if [[ -n "$VENV_PATH" ]]; then
    return
  fi

  if [[ -d "$DEFAULT_VENV_PATH" ]]; then
    VENV_PATH="$DEFAULT_VENV_PATH"
    return
  fi

  if [[ -d "$REPO_ROOT/venv" ]]; then
    VENV_PATH="$REPO_ROOT/venv"
    return
  fi

  fail "missing virtual environment. Create one first and pass --venv /absolute/path/to/.venv"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv)
      [[ $# -ge 2 ]] || fail "--venv requires a value"
      VENV_PATH="$2"
      shift 2
      ;;
    --config)
      [[ $# -ge 2 ]] || fail "--config requires a value"
      CONFIG_PATH="$2"
      shift 2
      ;;
    --state-dir)
      [[ $# -ge 2 ]] || fail "--state-dir requires a value"
      STATE_DIR="$2"
      shift 2
      ;;
    --host-id)
      [[ $# -ge 2 ]] || fail "--host-id requires a value"
      HOST_ID="$2"
      shift 2
      ;;
    --watch-file)
      [[ $# -ge 2 ]] || fail "--watch-file requires a value"
      WATCH_FILES+=("$2")
      shift 2
      ;;
    --force-config)
      FORCE_CONFIG=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

[[ "$(uname -s)" == "Linux" ]] || fail "WatchClaw install.sh currently supports Linux only"
[[ "$EUID" -eq 0 ]] || fail "run this installer as root (for /etc, /var/lib, systemd, and first scan access)"
[[ -f "$REPO_ROOT/pyproject.toml" ]] || fail "repo root does not look like a WatchClaw checkout: $REPO_ROOT"

require_command systemctl
require_command install
require_command sed
require_command ss

if ! command -v journalctl >/dev/null 2>&1; then
  warn "journalctl not found; auth monitoring will rely on logfile fallback only"
fi

resolve_venv_path
VENV_PATH="$(cd "$VENV_PATH" && pwd)"
WATCHCLAW_BIN="$VENV_PATH/bin/watchclaw"
VENV_PYTHON="$VENV_PATH/bin/python3"

[[ -d "$VENV_PATH" ]] || fail "virtual environment not found: $VENV_PATH"
[[ -x "$VENV_PYTHON" ]] || fail "missing virtualenv python: $VENV_PYTHON"
[[ -x "$WATCHCLAW_BIN" ]] || fail "missing watchclaw entrypoint in $VENV_PATH. Activate the venv and run: pip3 install -r requirements.txt && pip3 install ."

if ! "$WATCHCLAW_BIN" --help >/dev/null 2>&1; then
  fail "watchclaw CLI from $WATCHCLAW_BIN is not runnable"
fi

if ! "$VENV_PYTHON" -c 'import watchclaw' >/dev/null 2>&1; then
  fail "watchclaw package is not importable from $VENV_PYTHON. Activate the venv and run: pip3 install ."
fi

CONFIG_DIR="$(dirname "$CONFIG_PATH")"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_TEMPLATE="$REPO_ROOT/systemd/watchclaw.service"
TIMER_TEMPLATE="$REPO_ROOT/systemd/watchclaw.timer"
SERVICE_PATH="$SYSTEMD_DIR/watchclaw.service"
TIMER_PATH="$SYSTEMD_DIR/watchclaw.timer"

log "using virtual environment: $VENV_PATH"
log "creating config and state directories"
install -d -m 0755 "$CONFIG_DIR" "$STATE_DIR"

if [[ -e "$CONFIG_PATH" && "$FORCE_CONFIG" -ne 1 ]]; then
  log "keeping existing config at $CONFIG_PATH"
else
  TMP_CONFIG="$(mktemp)"
  CONFIG_ARGS=(init-config --output "$TMP_CONFIG" --force --host-id "$HOST_ID" --base-dir "$STATE_DIR")
  for watched_file in "${WATCH_FILES[@]}"; do
    CONFIG_ARGS+=(--watch-file "$watched_file")
  done

  log "writing config to $CONFIG_PATH"
  "$WATCHCLAW_BIN" "${CONFIG_ARGS[@]}"
  install -m 0644 "$TMP_CONFIG" "$CONFIG_PATH"
  rm -f "$TMP_CONFIG"
fi

log "installing systemd units"
[[ -f "$SERVICE_TEMPLATE" ]] || fail "missing service template: $SERVICE_TEMPLATE"
[[ -f "$TIMER_TEMPLATE" ]] || fail "missing timer template: $TIMER_TEMPLATE"

sed \
  -e "s|@WATCHCLAW_BIN@|$WATCHCLAW_BIN|g" \
  -e "s|@WATCHCLAW_CONFIG@|$CONFIG_PATH|g" \
  "$SERVICE_TEMPLATE" > "$SERVICE_PATH"
install -m 0644 "$TIMER_TEMPLATE" "$TIMER_PATH"
chmod 0644 "$SERVICE_PATH" "$TIMER_PATH"

log "reloading systemd"
systemctl daemon-reload

log "running first scan"
"$WATCHCLAW_BIN" run-once --config "$CONFIG_PATH"

log "enabling and starting timer"
systemctl enable --now watchclaw.timer

cat <<EOF

WatchClaw install complete.

Virtual env:    $VENV_PATH
Entrypoint:     $WATCHCLAW_BIN
Config:         $CONFIG_PATH
State dir:      $STATE_DIR
Service unit:   $SERVICE_PATH
Timer unit:     $TIMER_PATH

Verification hints:
  sudo $WATCHCLAW_BIN status --config $CONFIG_PATH
  systemctl status watchclaw.timer watchclaw.service
  systemctl list-timers watchclaw.timer
  journalctl -u watchclaw.service -n 50 --no-pager
  ls -la $STATE_DIR

Notes:
- first run mainly establishes baselines; some drift events only appear on later runs
- to update WatchClaw later, reactivate the same venv, run pip3 install ., then rerun this installer
EOF
