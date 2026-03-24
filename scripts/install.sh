#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_CONFIG_PATH="/etc/watchclaw/config.json"
DEFAULT_STATE_DIR="/var/lib/watchclaw"
DEFAULT_HOST_ID="$(hostname)"
CONFIG_PATH="$DEFAULT_CONFIG_PATH"
STATE_DIR="$DEFAULT_STATE_DIR"
HOST_ID="$DEFAULT_HOST_ID"
FORCE_CONFIG=0
PIP_BREAK_SYSTEM_PACKAGES="${PIP_BREAK_SYSTEM_PACKAGES:-0}"
WATCH_FILES=()

usage() {
  cat <<'EOF'
Usage: sudo ./scripts/install.sh [options]

Minimal installer for a local WatchClaw host setup.
It installs the package from this checkout, writes a config,
creates the state directory, installs systemd units, runs one scan,
and enables the timer.

Options:
  --config PATH         Config path to write (default: /etc/watchclaw/config.json)
  --state-dir PATH      State directory (default: /var/lib/watchclaw)
  --host-id ID          Host identifier for generated config (default: hostname)
  --watch-file PATH     Add a watched file path (repeatable)
  --force-config        Overwrite an existing config file
  --help                Show this help

Environment:
  PIP_BREAK_SYSTEM_PACKAGES=1   Append --break-system-packages to pip install
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

while [[ $# -gt 0 ]]; do
  case "$1" in
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

require_command python3
require_command systemctl
require_command install
require_command ss

if ! command -v journalctl >/dev/null 2>&1; then
  warn "journalctl not found; auth monitoring will rely on logfile fallback only"
fi

if ! python3 -m pip --version >/dev/null 2>&1; then
  fail "python3 -m pip is not available; install pip for Python 3 first"
fi

PIP_ARGS=(python3 -m pip install --prefix /usr/local .)
if [[ "$PIP_BREAK_SYSTEM_PACKAGES" == "1" ]]; then
  PIP_ARGS=(python3 -m pip install --break-system-packages --prefix /usr/local .)
fi

log "installing WatchClaw package from $REPO_ROOT"
(
  cd "$REPO_ROOT"
  "${PIP_ARGS[@]}"
)

WATCHCLAW_BIN="$(command -v watchclaw || true)"
if [[ -z "$WATCHCLAW_BIN" && -x "/usr/local/bin/watchclaw" ]]; then
  WATCHCLAW_BIN="/usr/local/bin/watchclaw"
fi
[[ -n "$WATCHCLAW_BIN" ]] || fail "watchclaw CLI was not found in PATH after installation"
[[ -x "$WATCHCLAW_BIN" ]] || fail "installed watchclaw CLI is not executable: $WATCHCLAW_BIN"

CONFIG_DIR="$(dirname "$CONFIG_PATH")"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_TEMPLATE="$REPO_ROOT/systemd/watchclaw.service"
TIMER_TEMPLATE="$REPO_ROOT/systemd/watchclaw.timer"
SERVICE_PATH="$SYSTEMD_DIR/watchclaw.service"
TIMER_PATH="$SYSTEMD_DIR/watchclaw.timer"

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

Installed CLI: $WATCHCLAW_BIN
Config:        $CONFIG_PATH
State dir:     $STATE_DIR
Service unit:  $SERVICE_PATH
Timer unit:    $TIMER_PATH

Verification hints:
  watchclaw status --config $CONFIG_PATH
  systemctl status watchclaw.timer watchclaw.service
  systemctl list-timers watchclaw.timer
  journalctl -u watchclaw.service -n 50 --no-pager
  ls -la $STATE_DIR

Notes:
- first run mainly establishes baselines; some drift events only appear on later runs
- if your distro blocks system pip writes, rerun with PIP_BREAK_SYSTEM_PACKAGES=1 only if that is an explicit local choice
EOF
