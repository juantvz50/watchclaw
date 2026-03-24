from __future__ import annotations

import json
import os
import re
import subprocess
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


COMMON_AUTH_LOG_PATHS = (
    "/var/log/auth.log",
    "/var/log/secure",
)
FAILED_BURST_THRESHOLD = 3

_SUCCESS_PATTERN = re.compile(
    r"Accepted (?P<method>\S+) for (?P<username>\S+) from (?P<source_ip>\S+) port (?P<source_port>\d+)",
)
_INVALID_USER_PATTERN = re.compile(
    r"Invalid user (?P<username>\S+) from (?P<source_ip>\S+)(?: port (?P<source_port>\d+))?",
)
_FAILED_PASSWORD_PATTERN = re.compile(
    r"Failed password for (?:invalid user )?(?P<username>\S+) from (?P<source_ip>\S+) port (?P<source_port>\d+)",
)


@dataclass(frozen=True)
class AuthLogCursor:
    source: str | None = None
    journal_cursor: str | None = None
    file_path: str | None = None
    file_offset: int = 0
    file_inode: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuthSignal:
    kind: str
    summary: str
    severity: str
    details: dict[str, Any]
    explain: dict[str, Any]
    dedupe_key: str


class AuthCollectionError(RuntimeError):
    pass


def collect_auth_signals(
    journal_command: Iterable[str],
    previous_cursor: AuthLogCursor | None = None,
    auth_log_paths: Iterable[str] = COMMON_AUTH_LOG_PATHS,
) -> tuple[list[AuthSignal], AuthLogCursor]:
    previous_cursor = previous_cursor or AuthLogCursor()

    try:
        return collect_journal_auth_signals(journal_command, previous_cursor)
    except (FileNotFoundError, subprocess.CalledProcessError, AuthCollectionError, json.JSONDecodeError):
        return collect_file_auth_signals(auth_log_paths, previous_cursor)


def collect_journal_auth_signals(
    journal_command: Iterable[str], previous_cursor: AuthLogCursor
) -> tuple[list[AuthSignal], AuthLogCursor]:
    command = list(journal_command)
    if previous_cursor.source == "journal" and previous_cursor.journal_cursor:
        command.extend(["--after-cursor", previous_cursor.journal_cursor])

    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    signals, last_cursor = parse_journal_output(completed.stdout)
    cursor = AuthLogCursor(source="journal", journal_cursor=last_cursor or previous_cursor.journal_cursor)
    return signals, cursor


def parse_journal_output(output: str) -> tuple[list[AuthSignal], str | None]:
    messages: list[dict[str, Any]] = []
    last_cursor: str | None = None
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        entry = json.loads(line)
        last_cursor = entry.get("__CURSOR", last_cursor)
        if not is_ssh_journal_entry(entry):
            continue
        messages.append(entry)
    return parse_auth_messages(messages, source="journal"), last_cursor


def is_ssh_journal_entry(entry: dict[str, Any]) -> bool:
    identifier = str(entry.get("SYSLOG_IDENTIFIER", "")).lower()
    comm = str(entry.get("_COMM", "")).lower()
    unit = str(entry.get("_SYSTEMD_UNIT", "")).lower()
    message = str(entry.get("MESSAGE", "")).lower()
    return any(value.startswith("ssh") for value in (identifier, comm)) or "sshd" in unit or "sshd" in message


def collect_file_auth_signals(
    auth_log_paths: Iterable[str], previous_cursor: AuthLogCursor
) -> tuple[list[AuthSignal], AuthLogCursor]:
    chosen_path = select_auth_log_path(auth_log_paths)
    if chosen_path is None:
        raise AuthCollectionError("No supported auth log file found")

    path = Path(chosen_path)
    stat = path.stat()
    start_offset = 0
    if (
        previous_cursor.source == "file"
        and previous_cursor.file_path == str(path)
        and previous_cursor.file_inode == stat.st_ino
        and previous_cursor.file_offset <= stat.st_size
    ):
        start_offset = previous_cursor.file_offset

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(start_offset)
        chunk = handle.read()
        end_offset = handle.tell()

    signals = parse_auth_log_lines(chunk.splitlines(), source=f"logfile:{path}")
    cursor = AuthLogCursor(
        source="file",
        file_path=str(path),
        file_offset=end_offset,
        file_inode=stat.st_ino,
    )
    return signals, cursor


def select_auth_log_path(paths: Iterable[str]) -> str | None:
    for candidate in paths:
        if os.path.exists(candidate):
            return candidate
    return None


def parse_auth_messages(entries: list[dict[str, Any]], source: str) -> list[AuthSignal]:
    parsed: list[dict[str, Any]] = []
    for entry in entries:
        message = str(entry.get("MESSAGE", "")).strip()
        if not message:
            continue
        observed_at = str(entry.get("__REALTIME_TIMESTAMP", ""))
        parsed.append({
            "message": message,
            "source": source,
            "raw": entry,
            "observed_at": observed_at,
        })
    return _build_signals(parsed)


def parse_auth_log_lines(lines: Iterable[str], source: str) -> list[AuthSignal]:
    parsed: list[dict[str, Any]] = []
    for line in lines:
        message = line.strip()
        if not message or "sshd" not in message.lower():
            continue
        parsed.append({"message": message, "source": source, "raw": {"line": message}})
    return _build_signals(parsed)


def _build_signals(parsed_messages: list[dict[str, Any]]) -> list[AuthSignal]:
    signals: list[AuthSignal] = []
    failed_attempts: Counter[tuple[str, str]] = Counter()
    failed_examples: dict[tuple[str, str], dict[str, Any]] = {}

    for item in parsed_messages:
        message = item["message"]
        source = item["source"]
        raw = item["raw"]

        success = _SUCCESS_PATTERN.search(message)
        if success:
            method = success.group("method")
            username = success.group("username")
            source_ip = success.group("source_ip")
            source_port = int(success.group("source_port"))
            signals.append(
                AuthSignal(
                    kind="ssh_login_success",
                    summary=f"SSH login succeeded for {username} from {source_ip}",
                    severity="info",
                    details={
                        "username": username,
                        "source_ip": source_ip,
                        "source_port": source_port,
                        "auth_method": method,
                        "raw_message": message,
                    },
                    explain={
                        "source": source,
                        "match": "Accepted <method> for <user> from <ip> port <port>",
                    },
                    dedupe_key=f"ssh_login_success:{username}:{source_ip}:{method}",
                )
            )
            continue

        invalid = _INVALID_USER_PATTERN.search(message)
        if invalid:
            username = invalid.group("username")
            source_ip = invalid.group("source_ip")
            port = invalid.group("source_port")
            details = {
                "username": username,
                "source_ip": source_ip,
                "raw_message": message,
            }
            if port is not None:
                details["source_port"] = int(port)
            signals.append(
                AuthSignal(
                    kind="ssh_invalid_user",
                    summary=f"SSH invalid user attempt for {username} from {source_ip}",
                    severity="warning",
                    details=details,
                    explain={
                        "source": source,
                        "match": "Invalid user <user> from <ip>",
                    },
                    dedupe_key=f"ssh_invalid_user:{username}:{source_ip}",
                )
            )
            continue

        failed = _FAILED_PASSWORD_PATTERN.search(message)
        if failed:
            username = failed.group("username")
            source_ip = failed.group("source_ip")
            source_port = int(failed.group("source_port"))
            key = (source_ip, username)
            failed_attempts[key] += 1
            failed_examples.setdefault(
                key,
                {
                    "username": username,
                    "source_ip": source_ip,
                    "source_port": source_port,
                    "raw_message": message,
                    "source": source,
                },
            )

    for key, count in sorted(failed_attempts.items()):
        if count < FAILED_BURST_THRESHOLD:
            continue
        example = failed_examples[key]
        signals.append(
            AuthSignal(
                kind="ssh_failed_login_burst",
                summary=f"SSH failed login burst for {example['username']} from {example['source_ip']} ({count} attempts)",
                severity="warning",
                details={
                    "username": example["username"],
                    "source_ip": example["source_ip"],
                    "source_port": example["source_port"],
                    "attempt_count": count,
                    "threshold": FAILED_BURST_THRESHOLD,
                    "raw_message_example": example["raw_message"],
                },
                explain={
                    "source": example["source"],
                    "match": "count of 'Failed password' SSH auth messages in this incremental batch",
                    "comparison": f"emitted when attempts for the same source_ip + username reach {FAILED_BURST_THRESHOLD} or more in one incremental read",
                },
                dedupe_key=f"ssh_failed_login_burst:{example['username']}:{example['source_ip']}:{count}",
            )
        )

    return signals
