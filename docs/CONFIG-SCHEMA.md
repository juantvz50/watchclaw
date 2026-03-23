# Config Schema (MVP)

## Goal

Define the smallest configuration surface needed for the first runnable WatchClaw slice.

The MVP should configure only what is necessary to:
- collect listener snapshots
- persist baseline/state locally
- emit JSONL events
- keep future expansion possible without over-designing now

---

## Config file location

Proposed default:

- `/etc/watchclaw/config.json`

Development/local override may be allowed later, but the installation story should assume one explicit config file.

---

## MVP config shape

```json
{
  "host_id": "jc-server",
  "storage": {
    "base_dir": "/var/lib/watchclaw"
  },
  "collection": {
    "listeners": {
      "enabled": true,
      "command": ["ss", "-ltnup"]
    }
  },
  "runtime": {
    "mode": "timer"
  }
}
```

---

## Fields

### `host_id`

Type:
- string

Purpose:
- stable logical host identifier written into events and local state

Rules:
- should be human-readable
- should remain stable over time
- should not rely on ephemeral hostnames if avoidable

---

### `storage.base_dir`

Type:
- string

Purpose:
- root directory for baseline, state, and event logs

Initial default:
- `/var/lib/watchclaw`

Rules:
- must be writable by the runtime user
- must remain local-first

---

### `collection.listeners.enabled`

Type:
- boolean

Purpose:
- turn listener collection on/off

MVP expectation:
- `true`

---

### `collection.listeners.command`

Type:
- string array

Purpose:
- exact command used to collect listening sockets

Initial default:
- `["ss", "-ltnup"]`

Rules:
- explicit command improves traceability
- future distro compatibility handling may add fallbacks

---

### `runtime.mode`

Type:
- enum

Allowed values for MVP:
- `timer`

Purpose:
- make the operating model explicit

Note:
- daemon mode is intentionally out of MVP config scope

---

## Not in MVP config yet

Do **not** add these yet unless they become necessary for the first runnable slice:

- alert routing
- severity overrides
- watched file lists
- cron watchers
- journal filters
- allowlists / denylists
- dedupe windows
- cloud endpoints
- SQLite toggles

These will come later when their first implementation slice exists.

---

## Design principles

- The config should stay tiny.
- Every field should map to real code already planned.
- No speculative knobs.
- No premature generalization.

