from __future__ import annotations

import json
import socket
from copy import deepcopy
from pathlib import Path
from typing import Any

from .models import DEFAULT_CONFIG, WatchClawConfig


DEFAULT_CONFIG_PATH = Path("/etc/watchclaw/config.json")


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def build_default_config(
    host_id: str | None = None,
    base_dir: str | None = None,
    watched_files: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    raw = deepcopy(DEFAULT_CONFIG)
    raw["host_id"] = host_id or socket.gethostname()
    if base_dir is not None:
        raw["storage"]["base_dir"] = base_dir
    if watched_files is not None:
        raw["collection"]["files"]["paths"] = list(dict.fromkeys(str(path) for path in watched_files))
    return raw


def dump_config(config: dict[str, Any]) -> str:
    return json.dumps(config, indent=2) + "\n"


def write_default_config(
    destination: str | Path,
    *,
    force: bool = False,
    host_id: str | None = None,
    base_dir: str | None = None,
    watched_files: list[str] | tuple[str, ...] | None = None,
) -> Path:
    destination_path = Path(destination)
    if destination_path.exists() and not force:
        raise FileExistsError(f"Config already exists: {destination_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(
        dump_config(build_default_config(host_id=host_id, base_dir=base_dir, watched_files=watched_files)),
        encoding="utf-8",
    )
    return destination_path


def load_config(path: str | Path | None = None) -> WatchClawConfig:
    source_path = Path(path) if path else DEFAULT_CONFIG_PATH
    raw: dict[str, Any] = build_default_config()
    if source_path.exists():
        raw = _merge_dicts(raw, json.loads(source_path.read_text()))

    collection = raw.get("collection", {})
    listeners = collection.get("listeners", {})
    files = collection.get("files", {})
    auth = collection.get("auth", {})
    storage = raw.get("storage", {})
    runtime = raw.get("runtime", {})
    delivery = runtime.get("delivery", {}) if isinstance(runtime, dict) else {}
    return WatchClawConfig(
        host_id=str(raw["host_id"]),
        base_dir=str(storage["base_dir"]),
        listeners_enabled=bool(listeners.get("enabled", True)),
        listeners_command=tuple(str(part) for part in listeners.get("command", ["ss", "-ltnup"])),
        listener_ignore_process_names=tuple(str(name) for name in listeners.get("ignore_process_names", [])),
        listener_ignore_local_ports=tuple(int(port) for port in listeners.get("ignore_local_ports", [])),
        watched_files=tuple(str(path) for path in files.get("paths", [])),
        auth_enabled=bool(auth.get("enabled", True)),
        auth_journal_command=tuple(
            str(part) for part in auth.get("journal_command", ["journalctl", "-q", "-o", "json", "--no-pager"])
        ),
        auth_log_paths=tuple(str(path) for path in auth.get("log_paths", ["/var/log/auth.log", "/var/log/secure"])),
        telegram_delivery_inline=bool(delivery.get("telegram_inline", True)),
    )
