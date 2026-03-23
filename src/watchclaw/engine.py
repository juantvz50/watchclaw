from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .listeners import collect_listener_snapshot
from .models import SCHEMA_VERSION, ListenerRecord, WatchClawConfig


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_listener_baseline(path: Path) -> list[ListenerRecord]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    listeners = payload.get("listeners", [])
    return sorted(ListenerRecord(**item) for item in listeners)


def write_listener_baseline(path: Path, captured_at: str, listeners: list[ListenerRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": captured_at,
        "listeners": [record.to_dict() for record in listeners],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def diff_listeners(previous: list[ListenerRecord], current: list[ListenerRecord]) -> tuple[list[ListenerRecord], list[ListenerRecord]]:
    previous_set = set(previous)
    current_set = set(current)
    added = sorted(current_set - previous_set)
    removed = sorted(previous_set - current_set)
    return added, removed


def build_event(kind: str, record: ListenerRecord, host_id: str, observed_at: str) -> dict[str, object]:
    change_text = {
        "new_listener": "present in current snapshot, absent in previous baseline",
        "listener_removed": "present in previous baseline, absent in current snapshot",
    }[kind]
    action = {
        "new_listener": "New listening socket detected",
        "listener_removed": "Listening socket removed",
    }[kind]
    listener = f"{record.local_address}:{record.local_port}/{record.proto}"
    process_suffix = f" ({record.process_name})" if record.process_name else ""
    dedupe_process = record.process_name or "unknown"
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid4()),
        "kind": kind,
        "severity": "warning",
        "host_id": host_id,
        "observed_at": observed_at,
        "summary": f"{action} on {listener}{process_suffix}",
        "details": asdict(record),
        "explain": {
            "source": "ss -ltnup",
            "comparison": change_text,
        },
        "dedupe_key": f"{kind}:{record.proto}:{record.local_address}:{record.local_port}:{dedupe_process}",
    }


def append_events(path: Path, events: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


def write_state(path: Path, host_id: str, last_run_at: str, last_success_at: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "host_id": host_id,
        "last_run_at": last_run_at,
        "last_success_at": last_success_at,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def run_listener_slice(config: WatchClawConfig) -> dict[str, int]:
    if not config.listeners_enabled:
        return {"listeners": 0, "events": 0}

    now = utc_now()
    observed_at = format_timestamp(now)
    base_dir = Path(config.base_dir)
    baseline_path = base_dir / "baselines" / "listeners.json"
    events_path = base_dir / "events.jsonl"
    state_path = base_dir / "state.json"

    previous = load_listener_baseline(baseline_path)
    current = collect_listener_snapshot(config.listeners_command)
    added, removed = diff_listeners(previous, current)

    events = [build_event("new_listener", record, config.host_id, observed_at) for record in added]
    events.extend(build_event("listener_removed", record, config.host_id, observed_at) for record in removed)

    if events:
        append_events(events_path, events)
    write_listener_baseline(baseline_path, observed_at, current)
    write_state(state_path, config.host_id, observed_at, observed_at)
    return {"listeners": len(current), "events": len(events)}
