from __future__ import annotations

import os
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from . import __version__

PACKAGE_NAME = "watchclaw"
DEFAULT_SERVICE_PATH = Path("/etc/systemd/system/watchclaw.service")
DEFAULT_TIMER_PATH = Path("/etc/systemd/system/watchclaw.timer")


def detect_capabilities() -> dict[str, bool]:
    return {
        "listener_monitoring": True,
        "file_integrity_monitoring": True,
        "auth_monitoring": True,
        "telegram_rendering": True,
        "telegram_delivery_prepare": True,
        "telegram_delivery_ack": True,
        "inline_telegram_delivery": True,
        "jsonl_chain_inspection": True,
        "systemd_timer_install": True,
    }


def read_systemd_execstart(service_path: Path = DEFAULT_SERVICE_PATH) -> str | None:
    if not service_path.exists():
        return None
    for line in service_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("ExecStart="):
            return line.removeprefix("ExecStart=").strip()
    return None


def get_git_head(repo_root: Path | None = None) -> dict[str, object] | None:
    candidate_root = repo_root or Path(__file__).resolve().parents[2]
    if not (candidate_root / ".git").exists():
        return None
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=candidate_root, text=True).strip()
        short_commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=candidate_root, text=True).strip()
        dirty = subprocess.run(["git", "diff", "--quiet"], cwd=candidate_root, check=False).returncode != 0
        return {
            "repo_root": str(candidate_root),
            "commit": commit,
            "short_commit": short_commit,
            "dirty": dirty,
        }
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def build_runtime_report(*, config_path: str, base_dir: str, host_id: str) -> dict[str, object]:
    service_execstart = read_systemd_execstart()
    try:
        installed_version = metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        installed_version = __version__

    git_head = get_git_head()
    return {
        "status": "ready",
        "host_id": host_id,
        "config_path": config_path,
        "base_dir": base_dir,
        "package_version": __version__,
        "installed_distribution_version": installed_version,
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "module_path": str(Path(__file__).resolve()),
        "cli_path": shutil.which("watchclaw"),
        "service_unit_path": str(DEFAULT_SERVICE_PATH),
        "service_unit_exists": DEFAULT_SERVICE_PATH.exists(),
        "timer_unit_path": str(DEFAULT_TIMER_PATH),
        "timer_unit_exists": DEFAULT_TIMER_PATH.exists(),
        "service_execstart": service_execstart,
        "running_from_systemd_unit": bool(service_execstart and os.path.realpath(sys.argv[0]) in service_execstart),
        "capabilities": detect_capabilities(),
        "git": git_head,
    }
