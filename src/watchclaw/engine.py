from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .auth import AuthLogCursor, collect_auth_signals
from .files import FileRecord, collect_file_snapshot
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


def load_file_baseline(path: Path) -> list[FileRecord]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    files = payload.get("files", [])
    return sorted(FileRecord(**item) for item in files)


def write_file_baseline(path: Path, captured_at: str, files: list[FileRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": captured_at,
        "files": [record.to_dict() for record in files],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def diff_listeners(previous: list[ListenerRecord], current: list[ListenerRecord]) -> tuple[list[ListenerRecord], list[ListenerRecord]]:
    previous_set = set(previous)
    current_set = set(current)
    added = sorted(current_set - previous_set)
    removed = sorted(previous_set - current_set)
    return added, removed


def diff_files(
    previous: list[FileRecord], current: list[FileRecord]
) -> tuple[list[FileRecord], list[FileRecord], list[tuple[FileRecord, FileRecord]]]:
    previous_by_path = {record.path: record for record in previous}
    current_by_path = {record.path: record for record in current}
    created: list[FileRecord] = []
    deleted: list[FileRecord] = []
    changed: list[tuple[FileRecord, FileRecord]] = []

    for path in sorted(set(previous_by_path) | set(current_by_path)):
        before = previous_by_path.get(path)
        after = current_by_path.get(path)
        if before is None and after is not None and after.exists:
            created.append(after)
            continue
        if before is not None and before.exists and (after is None or not after.exists):
            deleted.append(before)
            continue
        if before is not None and after is not None:
            if (before.exists != after.exists) and after.exists:
                created.append(after)
                continue
            if before.exists and after.exists and before.sha256 != after.sha256:
                changed.append((before, after))
    return created, deleted, changed


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


def build_file_event(
    kind: str,
    host_id: str,
    observed_at: str,
    current: FileRecord | None = None,
    previous: FileRecord | None = None,
) -> dict[str, object]:
    if current is None and previous is None:
        raise ValueError("build_file_event requires current or previous record")
    record = current or previous
    assert record is not None

    severity = {
        "watched_file_created": "warning",
        "watched_file_deleted": "critical",
        "sensitive_file_hash_changed": "critical",
    }[kind]
    summary = {
        "watched_file_created": f"Watched file created: {record.path}",
        "watched_file_deleted": f"Watched file deleted: {record.path}",
        "sensitive_file_hash_changed": f"Sensitive file hash changed: {record.path}",
    }[kind]
    comparison = {
        "watched_file_created": "file exists in current snapshot, absent from previous baseline",
        "watched_file_deleted": "file existed in previous baseline, absent from current snapshot",
        "sensitive_file_hash_changed": "file exists in both snapshots but content hash differs from previous baseline",
    }[kind]
    details = {"path": record.path}
    if previous is not None:
        details["previous"] = previous.to_dict()
    if current is not None:
        details["current"] = current.to_dict()
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid4()),
        "kind": kind,
        "severity": severity,
        "host_id": host_id,
        "observed_at": observed_at,
        "summary": summary,
        "details": details,
        "explain": {
            "source": "files.snapshot",
            "comparison": comparison,
        },
        "dedupe_key": f"{kind}:{record.path}",
    }


def build_auth_event(kind: str, details: dict[str, object], host_id: str, observed_at: str, explain: dict[str, object], summary: str, dedupe_key: str, severity: str) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid4()),
        "kind": kind,
        "severity": severity,
        "host_id": host_id,
        "observed_at": observed_at,
        "summary": summary,
        "details": details,
        "explain": explain,
        "dedupe_key": dedupe_key,
    }


def append_events(path: Path, events: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def write_state(
    path: Path,
    host_id: str,
    last_run_at: str,
    last_success_at: str,
    auth_cursor: AuthLogCursor | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = load_state(path)
    payload.update(
        {
            "schema_version": SCHEMA_VERSION,
            "host_id": host_id,
            "last_run_at": last_run_at,
            "last_success_at": last_success_at,
        }
    )
    if auth_cursor is not None:
        payload["auth_cursor"] = auth_cursor.to_dict()
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


def run_once(config: WatchClawConfig) -> dict[str, int]:
    now = utc_now()
    observed_at = format_timestamp(now)
    base_dir = Path(config.base_dir)
    events_path = base_dir / "events.jsonl"
    state_path = base_dir / "state.json"
    events: list[dict[str, object]] = []
    existing_state = load_state(state_path)

    listener_count = 0
    if config.listeners_enabled:
        listener_baseline_path = base_dir / "baselines" / "listeners.json"
        previous_listeners = load_listener_baseline(listener_baseline_path)
        current_listeners = collect_listener_snapshot(config.listeners_command)
        listener_count = len(current_listeners)
        added, removed = diff_listeners(previous_listeners, current_listeners)
        events.extend(build_event("new_listener", record, config.host_id, observed_at) for record in added)
        events.extend(build_event("listener_removed", record, config.host_id, observed_at) for record in removed)
        write_listener_baseline(listener_baseline_path, observed_at, current_listeners)

    file_count = 0
    if config.watched_files:
        files_baseline_path = base_dir / "baselines" / "files.json"
        previous_files = load_file_baseline(files_baseline_path)
        current_files = collect_file_snapshot(config.watched_files)
        file_count = len(current_files)
        created, deleted, changed = diff_files(previous_files, current_files)
        events.extend(build_file_event("watched_file_created", config.host_id, observed_at, current=record) for record in created)
        events.extend(build_file_event("watched_file_deleted", config.host_id, observed_at, previous=record) for record in deleted)
        events.extend(
            build_file_event(
                "sensitive_file_hash_changed",
                config.host_id,
                observed_at,
                previous=before,
                current=after,
            )
            for before, after in changed
        )
        write_file_baseline(files_baseline_path, observed_at, current_files)

    auth_count = 0
    auth_cursor = None
    if config.auth_enabled:
        previous_auth_cursor = AuthLogCursor(**existing_state.get("auth_cursor", {})) if existing_state.get("auth_cursor") else None
        auth_signals, auth_cursor = collect_auth_signals(
            config.auth_journal_command,
            previous_cursor=previous_auth_cursor,
            auth_log_paths=config.auth_log_paths,
        )
        auth_count = len(auth_signals)
        events.extend(
            build_auth_event(
                signal.kind,
                signal.details,
                config.host_id,
                observed_at,
                signal.explain,
                signal.summary,
                signal.dedupe_key,
                signal.severity,
            )
            for signal in auth_signals
        )

    if events:
        append_events(events_path, events)
    write_state(state_path, config.host_id, observed_at, observed_at, auth_cursor=auth_cursor)
    return {"listeners": listener_count, "files": file_count, "auth": auth_count, "events": len(events)}
