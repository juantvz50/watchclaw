from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable

from .models import ListenerRecord

_USERS_PATTERN = re.compile(r'\("(?P<name>[^\"]+)"(?:,pid=(?P<pid>\d+))?')


def collect_listener_snapshot(command: Iterable[str]) -> list[ListenerRecord]:
    completed = subprocess.run(
        list(command),
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_ss_output(completed.stdout)


def parse_ss_output(output: str) -> list[ListenerRecord]:
    records: set[ListenerRecord] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("Netid "):
            continue
        record = parse_ss_line(line)
        if record is not None:
            records.add(record)
    return sorted(records)


def parse_ss_line(line: str) -> ListenerRecord | None:
    parts = line.split()
    if len(parts) < 5:
        return None

    proto = parts[0].lower()
    local = parts[4]
    local_address, local_port = split_address_port(local)
    process_name, pid = extract_process(parts[6] if len(parts) >= 7 else "")

    return ListenerRecord(
        proto=proto,
        local_address=local_address,
        local_port=local_port,
        process_name=process_name,
        pid=pid,
    )


def split_address_port(value: str) -> tuple[str, int]:
    if value.startswith("[") and "]:" in value:
        address, _, port = value[1:].rpartition("]:")
        return normalize_address(address), int(port)
    address, _, port = value.rpartition(":")
    if not address or not port:
        raise ValueError(f"Unable to parse listener address: {value}")
    return normalize_address(address), int(port)


def normalize_address(value: str) -> str:
    if "%" in value:
        value = value.split("%", 1)[0]
    return value


def extract_process(process_field: str) -> tuple[str | None, int | None]:
    match = _USERS_PATTERN.search(process_field)
    if not match:
        return None, None
    pid = match.group("pid")
    return match.group("name"), int(pid) if pid else None
