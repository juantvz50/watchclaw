# Config Schema (MVP)

## Goal

Define the smallest configuration surface needed for the current runnable WatchClaw slices.

The MVP should configure only what is necessary to:
- collect listener snapshots
- collect watched-file snapshots
- read SSH/auth activity incrementally
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
    },
    "files": {
      "paths": [
        "/etc/ssh/sshd_config",
        "/etc/ssh/sshd_config.d/*.conf",
        "/etc/passwd",
        "/etc/group",
        "/etc/shadow",
        "/etc/gshadow",
        "/etc/sudoers",
        "/etc/sudoers.d/*",
        "/etc/crontab",
        "/etc/cron.d/*",
        "/root/.ssh/authorized_keys",
        "/home/*/.ssh/authorized_keys"
      ]
    },
    "auth": {
      "enabled": true,
      "journal_command": ["journalctl", "-q", "-o", "json", "--no-pager"],
      "log_paths": ["/var/log/auth.log", "/var/log/secure"]
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

### `collection.files.paths`

Type:
- string array

Purpose:
- exact file paths to snapshot for integrity monitoring

MVP expectation:
- operator-first defaults for core Linux security paths
- may include both literal paths and honest glob patterns for families like `sudoers.d` and home-directory `authorized_keys`

Rules:
- paths should stay human-auditable
- missing literal files are still tracked so create/delete drift is visible
- glob patterns expand to existing concrete files at collection time; unmatched globs are ignored rather than recorded as fake missing files

---

### `collection.auth.enabled`

Type:
- boolean

Purpose:
- turn SSH/auth monitoring on/off

Default:
- `true`

---

### `collection.auth.journal_command`

Type:
- string array

Purpose:
- exact command used for incremental journal reads when `journalctl` is available

Initial default:
- `["journalctl", "-q", "-o", "json", "--no-pager"]`

Rules:
- keep explicit for traceability
- WatchClaw appends `--after-cursor <cursor>` when it has a saved journal cursor
- if journal collection fails, WatchClaw falls back to auth logfile reading

---

### `collection.auth.log_paths`

Type:
- string array

Purpose:
- ordered fallback auth logfile paths for systems that do not expose the needed journal history

Initial default:
- `["/var/log/auth.log", "/var/log/secure"]`

Rules:
- first existing path wins
- file offset and inode are persisted locally for incremental reads
- keep paths explicit; no globs in MVP

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

Do **not** add these yet unless they become necessary for the current runnable slices:

- alert routing
- severity overrides
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
