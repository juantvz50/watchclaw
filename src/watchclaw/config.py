from __future__ import annotations

import json
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


def load_config(path: str | Path | None = None) -> WatchClawConfig:
    source_path = Path(path) if path else DEFAULT_CONFIG_PATH
    raw: dict[str, Any] = deepcopy(DEFAULT_CONFIG)
    if source_path.exists():
        raw = _merge_dicts(raw, json.loads(source_path.read_text()))

    listeners = raw.get("collection", {}).get("listeners", {})
    storage = raw.get("storage", {})
    return WatchClawConfig(
        host_id=str(raw["host_id"]),
        base_dir=str(storage["base_dir"]),
        listeners_enabled=bool(listeners.get("enabled", True)),
        listeners_command=tuple(str(part) for part in listeners.get("command", ["ss", "-ltnup"])),
    )
