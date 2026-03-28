# Telegram Delivery Preparation Layer

## Purpose

Bridge local WatchClaw event detection to outbound human-facing Telegram notifications without making the core detector depend on live Telegram transport.

This layer is intentionally split into two phases:

1. **prepare** — select notification-worthy unsent events, render Telegram payloads, persist delivery state
2. **acknowledge** — after some external sender actually delivers or fails the batch, mark the batch `sent` or `failed`

That keeps the repo local-first, inspectable, and explicit about what still belongs to OpenClaw or another sender.

## Default notification policy

By default, Telegram delivery is for events that are both:

- one of these kinds:
  - `new_listener`
  - `listener_removed`
  - `watched_file_created`
  - `watched_file_deleted`
  - `sensitive_file_hash_changed`
  - `ssh_invalid_user`
  - `ssh_failed_login_burst`
- and one of these severities:
  - `warning`
  - `critical`

### Journal-only by default

These still stay in `events.jsonl`, but they are **not** pushed to Telegram by default:

- `ssh_login_success`
- anything with severity `info`

Reason: those are useful for local traceability and search, but they are too noisy for default push delivery.

## Local state files

Delivery prep writes additional local files under `storage.base_dir`:

```text
<base_dir>/
  delivery-state.json
  deliveries.jsonl
```

### `delivery-state.json`

Durable per-event status for the Telegram channel.

Statuses currently used:
- `pending` — not yet handled by the delivery layer
- `prepared` — selected and rendered into a batch, waiting for transport acknowledgement
- `sent` — externally confirmed as delivered
- `failed` — transport attempted but failed
- `skipped` — intentionally excluded by default policy

### `deliveries.jsonl`

Append-only local log of delivery-side actions, for example:
- preparing a batch
- skipping an event as journal-only
- acknowledging a batch as sent/failed
- writing delivery state

## CLI

Prepare a batch:

```bash
watchclaw prepare-telegram-delivery --config /etc/watchclaw/config.json
```

Prepare at most two events:

```bash
watchclaw prepare-telegram-delivery --config /etc/watchclaw/config.json --limit 2
```

Re-include already-prepared events if an external sender crashed before acknowledgement:

```bash
watchclaw prepare-telegram-delivery --config /etc/watchclaw/config.json --include-prepared
```

Acknowledge a batch after transport succeeds:

```bash
watchclaw ack-telegram-delivery \
  --config /etc/watchclaw/config.json \
  --batch-id 3f7d... \
  --status sent
```

Acknowledge a batch failure:

```bash
watchclaw ack-telegram-delivery \
  --config /etc/watchclaw/config.json \
  --batch-id 3f7d... \
  --status failed \
  --reason "telegram bridge timeout"
```

## Output contract

`prepare-telegram-delivery` returns JSON like:

```json
{
  "status": "ok",
  "channel": "telegram",
  "batch_id": "...",
  "prepared_at": "2026-03-28T18:00:00Z",
  "prepared_count": 2,
  "skipped_count": 3,
  "deliveries": [
    {
      "delivery_id": "...",
      "batch_id": "...",
      "channel": "telegram",
      "prepared_at": "2026-03-28T18:00:00Z",
      "event_id": "evt-1",
      "event_kind": "watched_file_deleted",
      "event_severity": "critical",
      "decision": {
        "should_notify": true,
        "reason": "kind and severity match the default Telegram notification policy"
      },
      "payload": {
        "parse_mode": "HTML",
        "text": "<b>...Telegram HTML...</b>",
        "disable_web_page_preview": true
      },
      "event": {"...": "raw event"}
    }
  ]
}
```

This output is the thin integration boundary.
An OpenClaw transport only needs to:

1. call `prepare-telegram-delivery`
2. send each `payload` to Telegram
3. call `ack-telegram-delivery --batch-id ... --status sent|failed`

## Why this shape

- avoids resending the same event forever
- keeps policy explicit and inspectable
- keeps the transport boundary narrow
- works even when this repo cannot directly call Telegram
- stays explainable: every event has a durable local status
