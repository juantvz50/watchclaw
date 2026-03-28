# Telegram Operational Message Layer

## Purpose

This layer turns raw WatchClaw events into concise, recognizable, searchable Telegram-ready payloads.

It does **not** require live Telegram integration.

That separation is intentional:
- **WatchClaw server / disk layer:** traceability, baselines, append-only logs, inspectability
- **Telegram layer:** human UX, recognizable operational summaries, searchable journal entries

## Design stance

A Telegram message should answer four things in a stable order:
1. severity / event class
2. what happened
3. what WatchClaw did
4. why it matters

It should also preserve traceability with:
- host id
- observed timestamp
- event id
- dedupe key
- source/comparison trace line
- stable search tags

## Output shape

`watchclaw render-telegram` emits JSON, not network traffic.

Single event render shape:

```json
{
  "channel": "telegram",
  "rendered_at": "2026-03-28T16:00:00Z",
  "event": {"...": "raw watchclaw event"},
  "payload": {
    "parse_mode": "HTML",
    "text": "<b>🔴 CRITICAL · WATCHCLAW · SENSITIVE FILE CHANGED</b>\n...",
    "disable_web_page_preview": true
  }
}
```

This makes it easy for OpenClaw or a later Telegram transport adapter to send the payload unchanged.

## Searchability

Every message includes stable hashtags, for example:
- `#watchclaw`
- `#ssh`
- `#auth`
- `#integrity`
- `#surface-change`
- `#severity_warning`
- `#host_jc_server`

The tags are deliberately repetitive. Telegram is a journal/search surface here, not just a push channel.

## CLI

Render one event object:

```bash
watchclaw render-telegram --event-json '{
  "event_id": "evt-1",
  "kind": "ssh_invalid_user",
  "severity": "warning",
  "host_id": "jc-server",
  "observed_at": "2026-03-28T16:05:00Z",
  "summary": "SSH invalid user attempt for oracle from 10.0.0.2",
  "details": {"username": "oracle", "source_ip": "10.0.0.2", "source_port": 2200},
  "explain": {"source": "journalctl", "comparison": "matched Invalid user pattern"},
  "dedupe_key": "ssh_invalid_user:oracle:10.0.0.2"
}'
```

Render a whole event log:

```bash
watchclaw render-telegram --event-file /var/lib/watchclaw/events.jsonl
```

## Formatting contract

The current formatter uses Telegram HTML parse mode and emits:
- severity icon + label
- `WATCHCLAW` marker
- normalized event-kind label
- host
- when
- what happened
- observed details
- what WatchClaw did
- why it matters
- trace line
- event id
- dedupe key
- stable hashtags

## Why this layer exists

Raw JSON events are good for baselines, storage, and audit.
They are not the ideal human-facing operational message.

This layer creates a first-class message object so downstream delivery can be simple, deterministic, and consistent.
