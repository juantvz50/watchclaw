#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_VENV_PATH="$REPO_ROOT/.venv"
DEFAULT_CONFIG_PATH="/etc/watchclaw/config.json"
VENV_PATH=""
CONFIG_PATH="$DEFAULT_CONFIG_PATH"
SKIP_GIT_PULL=0

usage() {
  cat <<'EOF'
Usage: sudo ./scripts/upgrade.sh [options]

Upgrade/redeploy an existing WatchClaw host install that uses a dedicated venv.
This script makes the supported update path explicit:
1. optionally git pull
2. reinstall WatchClaw into the chosen venv
3. rerender/reinstall systemd units via scripts/install.sh
4. print a runtime status report so you can confirm what is actually installed

Options:
  --venv PATH         Existing virtual environment to reuse (default: ./.venv)
  --config PATH       Existing config path to preserve (default: /etc/watchclaw/config.json)
  --skip-git-pull     Do not run git pull before reinstalling
  --help              Show this help
EOF
}

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

log() {
  printf '==> %s\n' "$*"
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
    --skip-git-pull)
      SKIP_GIT_PULL=1
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

[[ "$(uname -s)" == "Linux" ]] || fail "WatchClaw upgrade.sh currently supports Linux only"
[[ "$EUID" -eq 0 ]] || fail "run this upgrader as root so it can reinstall systemd units and validate the live service"
[[ -f "$REPO_ROOT/pyproject.toml" ]] || fail "repo root does not look like a WatchClaw checkout: $REPO_ROOT"
command -v git >/dev/null 2>&1 || fail "required command not found: git"

if [[ -z "$VENV_PATH" ]]; then
  VENV_PATH="$DEFAULT_VENV_PATH"
fi
VENV_PATH="$(cd "$VENV_PATH" && pwd)"
WATCHCLAW_BIN="$VENV_PATH/bin/watchclaw"
PIP_BIN="$VENV_PATH/bin/pip3"

[[ -d "$VENV_PATH" ]] || fail "virtual environment not found: $VENV_PATH"
[[ -x "$PIP_BIN" ]] || fail "missing pip3 in virtual environment: $PIP_BIN"

if [[ "$SKIP_GIT_PULL" -ne 1 ]]; then
  log "updating checkout"
  git -C "$REPO_ROOT" pull --ff-only
else
  log "skipping git pull"
fi

log "reinstalling WatchClaw into $VENV_PATH"
"$PIP_BIN" install -r "$REPO_ROOT/requirements.txt"
"$PIP_BIN" install --upgrade "$REPO_ROOT"

log "rerendering systemd units and preserving existing config"
bash "$REPO_ROOT/scripts/install.sh" --venv "$VENV_PATH" --config "$CONFIG_PATH"

log "runtime status after upgrade"
"$WATCHCLAW_BIN" status --config "$CONFIG_PATH"

cat <<EOF

WatchClaw upgrade complete.

Next checks:
  sudo $WATCHCLAW_BIN status --config $CONFIG_PATH
  sudo systemctl status watchclaw.timer watchclaw.service
  sudo journalctl -u watchclaw.service -n 50 --no-pager
EOF
