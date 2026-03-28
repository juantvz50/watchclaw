from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .audit import append_jsonl_record
from .models import SCHEMA_VERSION
from .telegram import render_event_notification


DELIVERY_CHANNEL_TELEGRAM = "telegram"
DELIVERY_STATUS_PENDING = "pending"
DELIVERY_STATUS_PREPARED = "prepared"
DELIVERY_STATUS_SENT = "sent"
DELIVERY_STATUS_SKIPPED = "skipped"
DELIVERY_STATUS_FAILED = "failed"

DEFAULT_NOTIFIABLE_KINDS = {
    "new_listener",
    "listener_removed",
    "watched_file_created",
    "watched_file_deleted",
    "sensitive_file_hash_changed",
    "ssh_invalid_user",
    "ssh_failed_login_burst",
}
DEFAULT_NOTIFIABLE_SEVERITIES = {"warning", "critical"}


@dataclass(frozen=True)
class DeliveryDecision:
    should_notify: bool
    reason: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_delivery_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "channels": {
            DELIVERY_CHANNEL_TELEGRAM: {
                "events": {},
            }
        },
    }


def load_delivery_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_delivery_state()
    payload = json.loads(path.read_text(encoding="utf-8"))
    merged = default_delivery_state()
    merged["channels"].update(payload.get("channels", {}))
    merged.update({key: value for key, value in payload.items() if key != "channels"})
    merged.setdefault("schema_version", SCHEMA_VERSION)
    merged["channels"].setdefault(DELIVERY_CHANNEL_TELEGRAM, {"events": {}})
    merged["channels"][DELIVERY_CHANNEL_TELEGRAM].setdefault("events", {})
    return merged


def write_delivery_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def event_delivery_status(state: dict[str, Any], event_id: str, channel: str = DELIVERY_CHANNEL_TELEGRAM) -> str:
    return str(state.get("channels", {}).get(channel, {}).get("events", {}).get(event_id, {}).get("status", DELIVERY_STATUS_PENDING))


def decide_telegram_delivery(event: dict[str, Any]) -> DeliveryDecision:
    kind = str(event.get("kind", ""))
    severity = str(event.get("severity", "warning")).lower()
    if kind not in DEFAULT_NOTIFIABLE_KINDS:
        return DeliveryDecision(False, f"kind {kind or 'unknown'} is journal-only by default")
    if severity not in DEFAULT_NOTIFIABLE_SEVERITIES:
        return DeliveryDecision(False, f"severity {severity or 'unknown'} is below the default Telegram threshold")
    return DeliveryDecision(True, "kind and severity match the default Telegram notification policy")


def iter_event_log(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def build_delivery_record(event: dict[str, Any], *, batch_id: str, prepared_at: str) -> dict[str, Any]:
    decision = decide_telegram_delivery(event)
    rendered = render_event_notification(event)
    return {
        "delivery_id": str(uuid4()),
        "batch_id": batch_id,
        "channel": DELIVERY_CHANNEL_TELEGRAM,
        "prepared_at": prepared_at,
        "event_id": event.get("event_id"),
        "event_kind": event.get("kind"),
        "event_severity": event.get("severity"),
        "dedupe_key": event.get("dedupe_key"),
        "decision": {
            "should_notify": decision.should_notify,
            "reason": decision.reason,
        },
        "payload": rendered["payload"],
        "event": event,
    }


def update_delivery_state_for_event(
    state: dict[str, Any],
    *,
    event: dict[str, Any],
    status: str,
    batch_id: str | None,
    timestamp: str,
    reason: str,
    channel: str = DELIVERY_CHANNEL_TELEGRAM,
) -> dict[str, Any]:
    channel_state = state.setdefault("channels", {}).setdefault(channel, {"events": {}})
    events = channel_state.setdefault("events", {})
    event_id = str(event.get("event_id", "unknown"))
    previous = events.get(event_id, {})
    attempts = int(previous.get("attempts", 0))
    if status in {DELIVERY_STATUS_PREPARED, DELIVERY_STATUS_FAILED}:
        attempts += 1
    events[event_id] = {
        "event_id": event_id,
        "kind": event.get("kind"),
        "severity": event.get("severity"),
        "dedupe_key": event.get("dedupe_key"),
        "status": status,
        "reason": reason,
        "batch_id": batch_id,
        "attempts": attempts,
        "last_updated_at": timestamp,
        "prepared_at": previous.get("prepared_at"),
        "sent_at": previous.get("sent_at"),
        "failed_at": previous.get("failed_at"),
        "skipped_at": previous.get("skipped_at"),
    }
    if status == DELIVERY_STATUS_PREPARED:
        events[event_id]["prepared_at"] = timestamp
    elif status == DELIVERY_STATUS_SENT:
        events[event_id]["sent_at"] = timestamp
    elif status == DELIVERY_STATUS_FAILED:
        events[event_id]["failed_at"] = timestamp
    elif status == DELIVERY_STATUS_SKIPPED:
        events[event_id]["skipped_at"] = timestamp
    return events[event_id]


def append_delivery_action(
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
            "kind": "watchclaw_delivery_action",
            "action": action,
            "status": status,
            "details": details,
            "explain": {
                "source": "watchclaw.delivery",
                "comparison": "append-only local delivery log for notification preparation and acknowledgement state",
            },
        },
    )


def prepare_telegram_deliveries_for_events(
    *,
    base_dir: Path,
    host_id: str,
    events: list[dict[str, Any]],
    limit: int | None = None,
    include_prepared: bool = False,
    batch_id: str | None = None,
    prepared_at: str | None = None,
) -> dict[str, Any]:
    observed_at = prepared_at or format_timestamp(utc_now())
    resolved_batch_id = batch_id or str(uuid4())
    state_path = base_dir / "delivery-state.json"
    delivery_log_path = base_dir / "deliveries.jsonl"
    state = load_delivery_state(state_path)

    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    allowed_existing_statuses = {DELIVERY_STATUS_PENDING}
    if include_prepared:
        allowed_existing_statuses.add(DELIVERY_STATUS_PREPARED)

    for event in events:
        decision = decide_telegram_delivery(event)
        current_status = event_delivery_status(state, str(event.get("event_id", "")))
        if not decision.should_notify:
            if current_status == DELIVERY_STATUS_PENDING:
                entry = update_delivery_state_for_event(
                    state,
                    event=event,
                    status=DELIVERY_STATUS_SKIPPED,
                    batch_id=None,
                    timestamp=observed_at,
                    reason=decision.reason,
                )
                append_delivery_action(
                    delivery_log_path,
                    host_id=host_id,
                    observed_at=observed_at,
                    action="skip_delivery",
                    status="ok",
                    details={"event_id": event.get("event_id"), "reason": decision.reason, "delivery_status": entry["status"]},
                )
            skipped.append({"event_id": event.get("event_id"), "reason": decision.reason, "status": current_status})
            continue
        if current_status not in allowed_existing_statuses:
            continue
        record = build_delivery_record(event, batch_id=resolved_batch_id, prepared_at=observed_at)
        selected.append(record)
        update_delivery_state_for_event(
            state,
            event=event,
            status=DELIVERY_STATUS_PREPARED,
            batch_id=resolved_batch_id,
            timestamp=observed_at,
            reason=record["decision"]["reason"],
        )
        append_delivery_action(
            delivery_log_path,
            host_id=host_id,
            observed_at=observed_at,
            action="prepare_delivery",
            status="ok",
            details={
                "batch_id": resolved_batch_id,
                "event_id": event.get("event_id"),
                "kind": event.get("kind"),
                "severity": event.get("severity"),
                "delivery_status": DELIVERY_STATUS_PREPARED,
            },
        )
        if limit is not None and len(selected) >= max(limit, 0):
            break

    write_delivery_state(state_path, state)
    append_delivery_action(
        delivery_log_path,
        host_id=host_id,
        observed_at=observed_at,
        action="write_delivery_state",
        status="ok",
        details={"path": str(state_path), "prepared_count": len(selected), "skipped_count": len(skipped)},
    )
    return {
        "status": "ok",
        "channel": DELIVERY_CHANNEL_TELEGRAM,
        "batch_id": resolved_batch_id,
        "prepared_at": observed_at,
        "prepared_count": len(selected),
        "skipped_count": len(skipped),
        "deliveries": selected,
    }


def prepare_pending_telegram_deliveries(
    *,
    base_dir: Path,
    host_id: str,
    limit: int | None = None,
    include_prepared: bool = False,
) -> dict[str, Any]:
    events_path = base_dir / "events.jsonl"
    return prepare_telegram_deliveries_for_events(
        base_dir=base_dir,
        host_id=host_id,
        events=iter_event_log(events_path),
        limit=limit,
        include_prepared=include_prepared,
    )


def acknowledge_telegram_delivery_batch(
    *,
    base_dir: Path,
    host_id: str,
    batch_id: str,
    status: str,
    event_ids: list[str] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    if status not in {DELIVERY_STATUS_SENT, DELIVERY_STATUS_FAILED}:
        raise ValueError("delivery status must be sent or failed")
    observed_at = format_timestamp(utc_now())
    state_path = base_dir / "delivery-state.json"
    delivery_log_path = base_dir / "deliveries.jsonl"
    events_path = base_dir / "events.jsonl"
    events_by_id = {str(event.get("event_id")): event for event in iter_event_log(events_path)}
    state = load_delivery_state(state_path)
    channel_events = state.get("channels", {}).get(DELIVERY_CHANNEL_TELEGRAM, {}).get("events", {})
    requested = set(event_ids or [])
    updated: list[dict[str, Any]] = []
    for event_id, entry in channel_events.items():
        if entry.get("batch_id") != batch_id:
            continue
        if requested and event_id not in requested:
            continue
        event = events_by_id.get(event_id, {"event_id": event_id, "kind": entry.get("kind"), "severity": entry.get("severity"), "dedupe_key": entry.get("dedupe_key")})
        persisted = update_delivery_state_for_event(
            state,
            event=event,
            status=status,
            batch_id=batch_id,
            timestamp=observed_at,
            reason=reason or f"delivery batch {batch_id} marked {status}",
        )
        append_delivery_action(
            delivery_log_path,
            host_id=host_id,
            observed_at=observed_at,
            action="ack_delivery",
            status="ok",
            details={"batch_id": batch_id, "event_id": event_id, "delivery_status": status, "reason": persisted["reason"]},
        )
        updated.append(persisted)
    write_delivery_state(state_path, state)
    append_delivery_action(
        delivery_log_path,
        host_id=host_id,
        observed_at=observed_at,
        action="write_delivery_state",
        status="ok",
        details={"path": str(state_path), "updated_count": len(updated), "delivery_status": status},
    )
    return {
        "status": "ok",
        "channel": DELIVERY_CHANNEL_TELEGRAM,
        "batch_id": batch_id,
        "delivery_status": status,
        "updated_count": len(updated),
        "updated": updated,
    }
