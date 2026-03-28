from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .audit import _canonical_json


TIMESTAMP_KEYS = ("recorded_at", "observed_at")


def _recompute_hash(record: dict[str, Any]) -> str | None:
    if "record_hash" not in record:
        return None
    body = dict(record)
    body.pop("record_hash", None)
    body.pop("_line_number", None)
    return __import__("hashlib").sha256(_canonical_json(body).encode("utf-8")).hexdigest()


def _tail_summary(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for record in records[-limit:]:
        entry = {
            "line": record.get("_line_number"),
            "record_hash": record.get("record_hash"),
        }
        for key in ("kind", "action", "summary", "path", "user", "severity"):
            if key in record and record.get(key) is not None:
                entry[key] = record.get(key)
        for key in TIMESTAMP_KEYS:
            if key in record and record.get(key) is not None:
                entry[key] = record.get(key)
                break
        summary.append(entry)
    return summary


def inspect_jsonl_chain(path: Path, *, tail: int = 5) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    exists = path.exists()
    if not exists:
        issues.append({"severity": "warning", "code": "missing_file", "message": f"{path} does not exist"})
        return {
            "path": str(path),
            "exists": False,
            "record_count": 0,
            "verified": False,
            "issues": issues,
            "tail": [],
        }

    raw = path.read_text(encoding="utf-8")
    if raw and not raw.endswith("\n"):
        issues.append({
            "severity": "warning",
            "code": "missing_final_newline",
            "message": "file does not end with a newline; last append may have been interrupted",
        })

    previous_record_hash = None
    saw_blank_line = False
    for line_number, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            saw_blank_line = True
            issues.append({
                "severity": "warning",
                "code": "blank_line",
                "line": line_number,
                "message": "blank line found inside append-only log",
            })
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            issues.append({
                "severity": "critical",
                "code": "invalid_json",
                "line": line_number,
                "message": f"invalid JSON at line {line_number}: {exc.msg}",
            })
            continue
        if not isinstance(record, dict):
            issues.append({
                "severity": "critical",
                "code": "non_object_record",
                "line": line_number,
                "message": "JSONL record is not an object",
            })
            continue

        record["_line_number"] = line_number
        stored_hash = record.get("record_hash")
        recomputed_hash = _recompute_hash(record)
        if stored_hash is None:
            issues.append({
                "severity": "critical",
                "code": "missing_record_hash",
                "line": line_number,
                "message": "record is missing record_hash",
            })
        elif recomputed_hash != stored_hash:
            issues.append({
                "severity": "critical",
                "code": "record_hash_mismatch",
                "line": line_number,
                "message": "record_hash does not match recomputed canonical hash",
            })

        linked_previous = record.get("previous_record_hash")
        if not records:
            if linked_previous is not None:
                issues.append({
                    "severity": "warning",
                    "code": "first_record_has_previous_hash",
                    "line": line_number,
                    "message": "first record should usually have previous_record_hash=null",
                })
        elif linked_previous != previous_record_hash:
            issues.append({
                "severity": "critical",
                "code": "chain_link_mismatch",
                "line": line_number,
                "message": "previous_record_hash does not match prior record_hash; possible truncation/reset/edit",
                "expected_previous_record_hash": previous_record_hash,
                "actual_previous_record_hash": linked_previous,
            })

        if saw_blank_line:
            issues.append({
                "severity": "warning",
                "code": "gap_before_record",
                "line": line_number,
                "message": "record appears after a blank-line gap; possible manual edit or interrupted write",
            })
            saw_blank_line = False

        if not any(record.get(key) for key in TIMESTAMP_KEYS):
            issues.append({
                "severity": "warning",
                "code": "missing_timestamp",
                "line": line_number,
                "message": "record has no recorded_at/observed_at timestamp field",
            })

        records.append(record)
        previous_record_hash = stored_hash

    issue_codes = {issue["code"] for issue in issues}
    return {
        "path": str(path),
        "exists": True,
        "record_count": len(records),
        "verified": len(records) > 0 and not any(issue["severity"] == "critical" for issue in issues),
        "head_record_hash": records[0].get("record_hash") if records else None,
        "tail_record_hash": records[-1].get("record_hash") if records else None,
        "obvious_truncation_or_reset": any(code in issue_codes for code in ("chain_link_mismatch", "invalid_json", "blank_line", "gap_before_record", "missing_final_newline")),
        "issues": issues,
        "tail": _tail_summary(records, tail),
    }
