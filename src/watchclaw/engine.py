from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .audit import append_jsonl_record, append_jsonl_records
from .auth import AuthLogCursor, collect_auth_signals
from .files import FileRecord, collect_file_snapshot
from .listeners import collect_listener_snapshot
from .delivery import prepare_telegram_deliveries_for_events
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


def append_events(path: Path, events: list[dict[str, object]]) -> list[dict[str, object]]:
    return append_jsonl_records(path, events)


def append_action(
    path: Path,
    *,
    host_id: str,
    observed_at: str,
    action: str,
    status: str,
    details: dict[str, object],
) -> dict[str, object]:
    return append_jsonl_record(
        path,
        {
            "schema_version": SCHEMA_VERSION,
            "host_id": host_id,
            "observed_at": observed_at,
            "kind": "watchclaw_action",
            "action": action,
            "status": status,
            "details": details,
            "explain": {
                "source": "watchclaw.runtime",
                "comparison": "append-only local action log of WatchClaw side effects; this is auditable history, not a tamper-proof ledger",
            },
        },
    )


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


def filter_expected_listeners(listeners: list[ListenerRecord], config: WatchClawConfig) -> list[ListenerRecord]:
    ignored_processes = set(config.listener_ignore_process_names)
    ignored_ports = set(config.listener_ignore_local_ports)
    filtered: list[ListenerRecord] = []
    for record in listeners:
        if record.process_name and record.process_name in ignored_processes:
            continue
        if record.local_port in ignored_ports:
            continue
        filtered.append(record)
    return filtered


def run_listener_slice(config: WatchClawConfig) -> dict[str, int]:
    if not config.listeners_enabled:
        return {"listeners": 0, "events": 0}

    now = utc_now()
    observed_at = format_timestamp(now)
    base_dir = Path(config.base_dir)
    baseline_path = base_dir / "baselines" / "listeners.json"
    events_path = base_dir / "events.jsonl"
    actions_path = base_dir / "actions.jsonl"
    state_path = base_dir / "state.json"

    previous = load_listener_baseline(baseline_path)
    current = filter_expected_listeners(collect_listener_snapshot(config.listeners_command), config)
    added, removed = diff_listeners(previous, current)

    events = [build_event("new_listener", record, config.host_id, observed_at) for record in added]
    events.extend(build_event("listener_removed", record, config.host_id, observed_at) for record in removed)

    if events:
        written_events = append_events(events_path, events)
        append_action(
            actions_path,
            host_id=config.host_id,
            observed_at=observed_at,
            action="append_events",
            status="ok",
            details={"count": len(written_events), "event_kinds": [event["kind"] for event in written_events]},
        )
    write_listener_baseline(baseline_path, observed_at, current)
    append_action(
        actions_path,
        host_id=config.host_id,
        observed_at=observed_at,
        action="write_listener_baseline",
        status="ok",
        details={"path": str(baseline_path), "listener_count": len(current)},
    )
    write_state(state_path, config.host_id, observed_at, observed_at)
    append_action(
        actions_path,
        host_id=config.host_id,
        observed_at=observed_at,
        action="write_state",
        status="ok",
        details={"path": str(state_path)},
    )
    return {"listeners": len(current), "events": len(events)}


def run_once(config: WatchClawConfig) -> dict[str, object]:
    now = utc_now()
    observed_at = format_timestamp(now)
    base_dir = Path(config.base_dir)
    events_path = base_dir / "events.jsonl"
    actions_path = base_dir / "actions.jsonl"
    state_path = base_dir / "state.json"
    events: list[dict[str, object]] = []
    existing_state = load_state(state_path)

    listener_count = 0
    if config.listeners_enabled:
        listener_baseline_path = base_dir / "baselines" / "listeners.json"
        previous_listeners = load_listener_baseline(listener_baseline_path)
        current_listeners = filter_expected_listeners(collect_listener_snapshot(config.listeners_command), config)
        listener_count = len(current_listeners)
        added, removed = diff_listeners(previous_listeners, current_listeners)
        events.extend(build_event("new_listener", record, config.host_id, observed_at) for record in added)
        events.extend(build_event("listener_removed", record, config.host_id, observed_at) for record in removed)
        write_listener_baseline(listener_baseline_path, observed_at, current_listeners)
        append_action(
            actions_path,
            host_id=config.host_id,
            observed_at=observed_at,
            action="write_listener_baseline",
            status="ok",
            details={"path": str(listener_baseline_path), "listener_count": len(current_listeners)},
        )

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
        append_action(
            actions_path,
            host_id=config.host_id,
            observed_at=observed_at,
            action="write_file_baseline",
            status="ok",
            details={"path": str(files_baseline_path), "file_count": len(current_files)},
        )

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

    prepared_deliveries: dict[str, object] | None = None
    if events:
        written_events = append_events(events_path, events)
        append_action(
            actions_path,
            host_id=config.host_id,
            observed_at=observed_at,
            action="append_events",
            status="ok",
            details={"count": len(written_events), "event_kinds": [event["kind"] for event in written_events]},
        )
        if config.telegram_delivery_inline:
            prepared_deliveries = prepare_telegram_deliveries_for_events(
                base_dir=base_dir,
                host_id=config.host_id,
                events=written_events,
                prepared_at=observed_at,
            )
    write_state(state_path, config.host_id, observed_at, observed_at, auth_cursor=auth_cursor)
    append_action(
        actions_path,
        host_id=config.host_id,
        observed_at=observed_at,
        action="write_state",
        status="ok",
        details={"path": str(state_path), "auth_cursor_written": auth_cursor is not None},
    )
    result: dict[str, object] = {"listeners": listener_count, "files": file_count, "auth": auth_count, "events": len(events)}
    if prepared_deliveries is not None:
        result["delivery"] = prepared_deliveries
    return result
