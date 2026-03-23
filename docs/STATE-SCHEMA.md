# State Schema (MVP)

## Goal

Define the local state layout needed to support the first runnable listener-diff slice.

The MVP state must support:
- previous listener baseline
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
  "last_success_at": "2026-03-23T22:00:00Z"
}
```

Rules:
- keep small
- no duplicated baseline payloads here
- no event history here

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
- journal cursor state
- dedupe caches
- file-hash baselines
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

