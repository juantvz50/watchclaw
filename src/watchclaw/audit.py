from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _last_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    last_line = ""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                last_line = stripped
    if not last_line:
        return None
    return json.loads(last_line).get("record_hash")


def append_jsonl_record(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous_hash = _last_hash(path)
    body = dict(payload)
    body["previous_record_hash"] = previous_hash
    body["record_hash"] = hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(body, ensure_ascii=False) + "\n")
    return body


def append_jsonl_records(path: Path, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    written: list[dict[str, Any]] = []
    for payload in payloads:
        written.append(append_jsonl_record(path, payload))
    return written
