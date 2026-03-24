# State Schema (MVP)

## Goal

Define the local state layout needed to support the current runnable slices.

The MVP state must support:
- previous listener baseline
- previous watched-file baseline
- incremental SSH/auth cursor state
- event append log
- simple recoverability

---

## State root

Derived from config:
- `<base_dir>/`

Initial expected files:

```text
/var/lib/watchclaw/
  state.json
  events.jsonl
  baselines/
    listeners.json
    files.json
```

---

## `state.json`

Purpose:
- hold lightweight runtime metadata

Initial shape:

```json
{
  "schema_version": 1,
  "host_id": "jc-server",
  "last_run_at": "2026-03-23T22:00:00Z",
  "last_success_at": "2026-03-23T22:00:00Z",
  "auth_cursor": {
    "source": "journal",
    "journal_cursor": "s=abc;i=123",
    "file_path": null,
    "file_offset": 0,
    "file_inode": null
  }
}
```

Rules:
- keep small
- no duplicated baseline payloads here
- no event history here
- `auth_cursor` stores either a journal cursor or logfile offset/inode, depending on which source was used last

---

## `baselines/listeners.json`

Purpose:
- store the last accepted listener snapshot

Initial shape:

```json
{
  "schema_version": 1,
  "captured_at": "2026-03-23T22:00:00Z",
  "listeners": [
    {
      "proto": "tcp",
      "local_address": "0.0.0.0",
      "local_port": 22,
      "process_name": "sshd",
      "pid": 123
    }
  ]
}
```

Rules:
- this is the source baseline for listener diffs
- normalized fields only
- stable ordering preferred for inspectability

---

## `baselines/files.json`

Purpose:
- store the last accepted watched-file snapshot

Initial shape:

```json
{
  "schema_version": 1,
  "captured_at": "2026-03-23T22:00:00Z",
  "files": [
    {
      "path": "/etc/sudoers",
      "exists": true,
      "sha256": "abc123",
      "size": 1710,
      "mode": 33184,
      "mtime_ns": 1711234567890123456
    }
  ]
}
```

Rules:
- this is the source baseline for watched-file diffs
- missing files remain explicit with `exists: false`
- content hash is the primary content-drift signal in MVP

---

## `events.jsonl`

Purpose:
- append-only event log

Format:
- one JSON object per line

Rules:
- every event must be independently readable
- event log should be human-inspectable
- no binary or compressed format in MVP

---

## Not in MVP state yet

Do **not** add these until needed:
- dedupe caches
- service/timer baselines
- alert delivery receipts
- cloud sync metadata

These belong to later slices.

---

## Design principles

- Keep state transparent.
- Keep baseline separate from metadata.
- Keep events append-only.
- Prefer inspectability over abstraction.
