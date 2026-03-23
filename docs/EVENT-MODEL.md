# Event Model (MVP)

## Goal

Define the smallest event model needed for the first WatchClaw runnable slice.

The first slice only needs to represent listener drift.

---

## Core event kinds in MVP

- `new_listener`
- `listener_removed`

No other kinds should be emitted in the first runnable slice.

---

## Event shape

```json
{
  "schema_version": 1,
  "event_id": "uuid-or-deterministic-id",
  "kind": "new_listener",
  "severity": "warning",
  "host_id": "jc-server",
  "observed_at": "2026-03-23T22:00:00Z",
  "summary": "New listening socket detected on 0.0.0.0:9000/tcp",
  "details": {
    "proto": "tcp",
    "local_address": "0.0.0.0",
    "local_port": 9000,
    "process_name": "python3",
    "pid": 4567
  },
  "explain": {
    "source": "ss -ltnup",
    "comparison": "present in current snapshot, absent in previous baseline"
  },
  "dedupe_key": "new_listener:tcp:0.0.0.0:9000:python3"
}
```

---

## Required fields

### `schema_version`
- integer

### `event_id`
- string
- unique per event record

### `kind`
- enum
- one of:
  - `new_listener`
  - `listener_removed`

### `severity`
- enum
- MVP values:
  - `warning`

Note:
- severity expansion happens later

### `host_id`
- string

### `observed_at`
- RFC3339 timestamp

### `summary`
- short human-readable sentence

### `details`
- normalized listener details

### `explain`
- compact explanation of why the event exists

### `dedupe_key`
- deterministic key for future dedupe behavior

---

## Explainability contract

Every event in MVP must answer:

1. What changed?
2. Compared to what?
3. From which source command?

If an emitted event cannot answer those three questions cleanly, the event model is wrong.

---

## Severity stance

For the first slice:
- `new_listener` => `warning`
- `listener_removed` => `warning`

Do not over-model severity before more event types exist.

---

## Design principles

- Events must be semantically meaningful.
- Events must be explainable from source facts.
- Events must be compact enough for human and LLM reading.
- Events must avoid raw log spam.

