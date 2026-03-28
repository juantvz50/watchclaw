from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SEVERITY_ICONS = {
    "info": "🔵",
    "warning": "🟠",
    "critical": "🔴",
}

SEVERITY_LABELS = {
    "info": "INFO",
    "warning": "WARNING",
    "critical": "CRITICAL",
}

KIND_LABELS = {
    "new_listener": "NEW LISTENER",
    "listener_removed": "LISTENER REMOVED",
    "watched_file_created": "WATCHED FILE CREATED",
    "watched_file_deleted": "WATCHED FILE DELETED",
    "sensitive_file_hash_changed": "SENSITIVE FILE CHANGED",
    "ssh_login_success": "SSH LOGIN SUCCESS",
    "ssh_invalid_user": "SSH INVALID USER",
    "ssh_failed_login_burst": "SSH FAILED LOGIN BURST",
}

WHY_IT_MATTERS = {
    "new_listener": "A new listening socket changes the host attack surface and deserves attribution.",
    "listener_removed": "A previously exposed service disappeared; this may be expected maintenance or an unplanned service change.",
    "watched_file_created": "A sensitive file appeared where WatchClaw expects stability; creation can indicate config drift or operator action.",
    "watched_file_deleted": "A watched security-relevant file disappeared; deletion can break controls or hide tampering.",
    "sensitive_file_hash_changed": "A watched file changed on disk; integrity drift on security-relevant files should be explained.",
    "ssh_login_success": "A successful SSH login is often legitimate, but it should still be part of the searchable operational journal.",
    "ssh_invalid_user": "Invalid-user probes are common reconnaissance and can indicate opportunistic scanning.",
    "ssh_failed_login_burst": "Multiple failed SSH attempts in one batch suggest active password guessing or noisy automation.",
}

ACTION_TAKEN = {
    "new_listener": "WatchClaw recorded the event and preserved the new listener baseline for future diffs.",
    "listener_removed": "WatchClaw recorded the event and updated the listener baseline to the current host state.",
    "watched_file_created": "WatchClaw recorded the event and refreshed the file baseline to preserve traceability.",
    "watched_file_deleted": "WatchClaw recorded the deletion and refreshed the file baseline so future runs stay explainable.",
    "sensitive_file_hash_changed": "WatchClaw recorded the before/after file metadata and refreshed the file baseline.",
    "ssh_login_success": "WatchClaw recorded the auth event in the append-only event log.",
    "ssh_invalid_user": "WatchClaw recorded the auth event in the append-only event log.",
    "ssh_failed_login_burst": "WatchClaw recorded the auth event in the append-only event log.",
}

SEARCH_TAGS = {
    "new_listener": ["#watchclaw", "#listener", "#surface-change"],
    "listener_removed": ["#watchclaw", "#listener", "#surface-change"],
    "watched_file_created": ["#watchclaw", "#file", "#integrity"],
    "watched_file_deleted": ["#watchclaw", "#file", "#integrity"],
    "sensitive_file_hash_changed": ["#watchclaw", "#file", "#integrity"],
    "ssh_login_success": ["#watchclaw", "#ssh", "#auth"],
    "ssh_invalid_user": ["#watchclaw", "#ssh", "#auth"],
    "ssh_failed_login_burst": ["#watchclaw", "#ssh", "#auth"],
}


@dataclass(frozen=True)
class TelegramMessagePayload:
    parse_mode: str
    text: str
    disable_web_page_preview: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "parse_mode": self.parse_mode,
            "text": self.text,
            "disable_web_page_preview": self.disable_web_page_preview,
        }


def _severity_label(event: dict[str, Any]) -> str:
    severity = str(event.get("severity", "warning")).lower()
    icon = SEVERITY_ICONS.get(severity, "⚪️")
    label = SEVERITY_LABELS.get(severity, severity.upper())
    return f"{icon} {label}"


def _kind_label(event: dict[str, Any]) -> str:
    kind = str(event.get("kind", "event"))
    return KIND_LABELS.get(kind, kind.replace("_", " ").upper())


def _escape_html(value: Any) -> str:
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _event_tags(event: dict[str, Any]) -> list[str]:
    kind = str(event.get("kind", ""))
    severity = str(event.get("severity", "warning")).lower()
    tags = list(SEARCH_TAGS.get(kind, ["#watchclaw"]))
    tags.append(f"#severity_{severity}")
    host_id = str(event.get("host_id", "unknown")).strip().replace("-", "_")
    tags.append(f"#host_{host_id}")
    return tags


def summarize_what_happened(event: dict[str, Any]) -> str:
    kind = str(event.get("kind", ""))
    details = event.get("details", {}) if isinstance(event.get("details"), dict) else {}

    if kind in {"new_listener", "listener_removed"}:
        proto = details.get("proto", "?")
        local_address = details.get("local_address", "?")
        local_port = details.get("local_port", "?")
        process_name = details.get("process_name") or "unknown process"
        pid = details.get("pid")
        pid_suffix = f" pid={pid}" if pid is not None else ""
        return f"{proto} {local_address}:{local_port} owned by {process_name}{pid_suffix}."

    if kind in {"watched_file_created", "watched_file_deleted", "sensitive_file_hash_changed"}:
        path = details.get("path", "unknown path")
        if kind == "sensitive_file_hash_changed":
            previous = details.get("previous", {}) if isinstance(details.get("previous"), dict) else {}
            current = details.get("current", {}) if isinstance(details.get("current"), dict) else {}
            before = previous.get("sha256", "unknown")
            after = current.get("sha256", "unknown")
            return f"{path} changed from sha256={before} to sha256={after}."
        if kind == "watched_file_created":
            return f"{path} now exists in the current snapshot and was absent before."
        return f"{path} existed before and is now missing from the current snapshot."

    if kind == "ssh_login_success":
        return (
            f"user={details.get('username', '?')} ip={details.get('source_ip', '?')} "
            f"method={details.get('auth_method', '?')} port={details.get('source_port', '?')}."
        )

    if kind == "ssh_invalid_user":
        port = details.get("source_port")
        port_suffix = f" port={port}" if port is not None else ""
        return f"username={details.get('username', '?')} ip={details.get('source_ip', '?')}{port_suffix}."

    if kind == "ssh_failed_login_burst":
        return (
            f"user={details.get('username', '?')} ip={details.get('source_ip', '?')} "
            f"attempts={details.get('attempt_count', '?')} threshold={details.get('threshold', '?')}."
        )

    summary = event.get("summary") or "WatchClaw observed an event."
    return f"{summary}"


def summarize_action_taken(event: dict[str, Any]) -> str:
    return ACTION_TAKEN.get(str(event.get("kind", "")), "WatchClaw recorded the event for traceability.")


def summarize_why_it_matters(event: dict[str, Any]) -> str:
    return WHY_IT_MATTERS.get(str(event.get("kind", "")), "This event changes the operational picture and should remain searchable.")


def render_telegram_text(event: dict[str, Any]) -> str:
    severity = _escape_html(_severity_label(event))
    kind = _escape_html(_kind_label(event))
    summary = _escape_html(event.get("summary", "WatchClaw event"))
    host_id = _escape_html(event.get("host_id", "unknown"))
    observed_at = _escape_html(event.get("observed_at", "unknown"))
    event_id = _escape_html(event.get("event_id", "unknown"))
    dedupe_key = _escape_html(event.get("dedupe_key", "unknown"))
    what_happened = _escape_html(summarize_what_happened(event))
    action_taken = _escape_html(summarize_action_taken(event))
    why_it_matters = _escape_html(summarize_why_it_matters(event))
    tags = " ".join(_escape_html(tag) for tag in _event_tags(event))

    explain = event.get("explain", {}) if isinstance(event.get("explain"), dict) else {}
    source = _escape_html(explain.get("source", "unknown"))
    comparison = _escape_html(explain.get("comparison", "not provided"))

    lines = [
        f"<b>{severity} · WATCHCLAW · {kind}</b>",
        f"<b>Host:</b> <code>{host_id}</code>",
        f"<b>When:</b> <code>{observed_at}</code>",
        f"<b>What happened:</b> {summary}",
        f"<b>Observed details:</b> {what_happened}",
        f"<b>What WatchClaw did:</b> {action_taken}",
        f"<b>Why it matters:</b> {why_it_matters}",
        f"<b>Trace:</b> source=<code>{source}</code> comparison=<code>{comparison}</code>",
        f"<b>Event ID:</b> <code>{event_id}</code>",
        f"<b>Dedupe:</b> <code>{dedupe_key}</code>",
        tags,
    ]
    return "\n".join(lines)


def build_telegram_payload(event: dict[str, Any]) -> TelegramMessagePayload:
    return TelegramMessagePayload(parse_mode="HTML", text=render_telegram_text(event))


def render_event_notification(event: dict[str, Any]) -> dict[str, Any]:
    payload = build_telegram_payload(event)
    return {
        "channel": "telegram",
        "rendered_at": event.get("observed_at"),
        "event": event,
        "payload": payload.to_dict(),
    }


def render_event_file(input_path: str | Path) -> list[dict[str, Any]]:
    path = Path(input_path)
    rendered: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        rendered.append(render_event_notification(json.loads(line)))
    return rendered
