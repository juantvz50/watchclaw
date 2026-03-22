# WatchClaw — Living Technical Document

## Status

Draft v0.1
Owner: JC (Project Manager)
Technical counterpart: Sedna
Project type: Open-source host watchdog for systems already running OpenClaw

---

## 1. Purpose

WatchClaw exists to monitor a Linux host in a way that is:

- lightweight
- explainable
- installable on an existing OpenClaw system
- readable by humans
- especially useful for LLM-assisted review and alerting

The core idea is not to become a full SIEM, nor to wrap heavyweight security tooling blindly.
The goal is to produce **structured, high-signal host observations** that can be:

- diffed
- summarized
- triaged
- explained
- escalated through OpenClaw

---

## 2. Product thesis

Traditional host security tools are often good at one of two things:

1. collecting low-level signals very reliably
2. enforcing specific security controls

But they are often weaker at:

- summarizing what actually changed
- correlating small host events into meaningful observations
- producing compact operator-friendly explanations
- adapting gracefully to a personal server/workstation context

Humans are too slow and inconsistent for constant log review.
Rule-only automation is fast but brittle.
LLMs are good at reading large structured outputs quickly and turning them into useful judgments.

Therefore WatchClaw should be designed as:

> a baseline + diff + structured event engine for host state, optimized for LLM/OpenClaw interpretation

Not as:

- a generic SIEM clone
- a full HIDS replacement
- an enterprise compliance product
- a magical auto-remediator

---

## 3. Project constraints

### 3.1 Must be installable on top of an existing OpenClaw host

Assume the target machine already has:

- Linux
- Python available or installable
- OpenClaw already running
- outbound network access at least intermittently

### 3.2 Must be understandable

A user should be able to answer:

- what WatchClaw is watching
- how it decides something changed
- why an alert was emitted
- how to rebuild baseline safely

### 3.3 Must degrade gracefully

If any optional integration fails:

- WatchClaw should still collect locally
- state should remain readable
- alerts can be retried or summarized later

### 3.4 Must prefer high-signal over high-volume

We care more about:

- meaningful diffs
- host changes
- suspicious transitions
- actionable summaries

than about collecting every kernel-level event from day one.

---

## 4. Non-goals

At least for the MVP, WatchClaw is **not** trying to be:

- Wazuh replacement
- osquery replacement
- auditd replacement
- EDR/XDR platform
- incident response suite
- automatic hardening tool
- active network IDS
- malware scanner
- filebeat/logstash pipeline clone

Also out of scope for MVP:

- full policy enforcement
- automated remediation by default
- multi-host fleet management
- complicated cloud control plane
- enterprise dashboards
- compliance frameworks

---

## 5. Architectural position

WatchClaw should sit in the following layer stack:

### Layer A — System truth
Native host interfaces and existing tools:

- `journalctl`
- auth logs / journald units
- `ss`
- `systemctl`
- cron data
- passwd/group/sudo/ssh files
- filesystem metadata / hashes
- optionally:
  - AIDE
  - minimal auditd
  - fail2ban state/signals

### Layer B — WatchClaw collection and normalization
WatchClaw gathers:

- snapshots
- incremental journal reads
- selected file integrity state
- selected system object state

Then normalizes them into structured records.

### Layer C — Baseline and diff engine
WatchClaw compares:

- previous known state
- current observed state

and produces semantic events such as:

- `new_listener`
- `service_failed`
- `ssh_login_new_ip`
- `ssh_key_added`
- `sensitive_file_hash_changed`
- `new_timer_unit`

### Layer D — Interpretation / alert routing
Events can then be:

- deduplicated
- grouped
- scored
- summarized
- routed to OpenClaw for human-facing alerting

### Layer E — Human / LLM consumption
Final output should be:

- compact
- explainable
- suitable for Telegram alerts
- suitable for daily digest
- suitable for LLM summarization without drowning in raw logs

---

## 6. Why not start with heavyweight tooling?

Because the project value is not “we know many existing security tool names.”
The value is a system that:

- is easy to install
- is easy to understand
- provides high-leverage visibility
- integrates naturally with OpenClaw
- keeps state compact enough for machine summarization

Heavyweight stacks tend to introduce early penalties:

- too much configuration
- too much data
- too many moving parts
- reduced explainability
- increased operator fatigue
- pressure to support a broad problem space too soon

This does **not** mean existing tools are useless.
It means they should be treated as optional signal providers, not as the product core.

---

## 7. Proposed technical direction

## 7.1 Language

Primary language: **Python**

Reasoning:

- fastest path to implementation
- easy subprocess integration with Linux tooling
- easy JSON/state handling
- easy hashing/parsing/diffing
- easy packaging for existing Linux hosts
- good fit for OpenClaw-adjacent scripting

At current project stage, Python is favored over Go/Rust because:

- speed of iteration matters more than binary purity
- the hard part is system design and signal modeling, not raw throughput
- subprocess + structured parsing is enough for MVP scale

---

## 7.2 Runtime model

Preferred model:

- long-lived lightweight service **or** periodic `systemd` timer execution

Initial recommendation:

### MVP recommendation
Use a **periodic runner** via `systemd timer`.

Why:

- simpler to reason about
- easier install/uninstall
- easier debugging
- natural fit for snapshot + diff design
- avoids daemon complexity too early

Potential cadence:

- every 1 minute for journal/incremental auth checks
- every 5 minutes for snapshots like listeners/services
- every 15–60 minutes for heavier integrity checks depending on configuration

We do not need a permanent daemon on day one unless latency requirements tighten.

---

## 7.3 State model

WatchClaw needs a durable local state store.

### Initial recommendation
Use local JSON/JSONL plus deterministic files.

Suggested structure:

```text
/var/lib/watchclaw/
  config.json
  state.json
  events.jsonl
  baselines/
    files.json
    listeners.json
    systemd.json
    users.json
```

### Principles
- baseline must be inspectable by humans
- event history must be append-friendly
- last processed journal cursor must be stored
- dedupe state must be explicit
- no opaque binary state in MVP

If scale later justifies it, move to SQLite.
But not before the data model is proven.

---

## 8. MVP functional scope

## 8.1 SSH / auth monitoring

Goal: detect meaningful remote access activity.

Signals:
- successful SSH login
- failed SSH login bursts
- login from IP not seen before
- invalid user attempts
- root login attempts
- sudo usage signals (carefully filtered)

Source:
- `journalctl` or auth logs, depending on distro

Output examples:
- `ssh_login_success`
- `ssh_login_new_ip`
- `ssh_failed_burst`
- `ssh_invalid_user_attempt`

---

## 8.2 Sensitive file integrity monitoring

Goal: notice high-value config/auth changes.

Initial watched paths:
- `/etc/ssh/sshd_config`
- `/etc/passwd`
- `/etc/group`
- `/etc/sudoers`
- `/etc/crontab`
- `/root/.ssh/authorized_keys`
- important user `authorized_keys` files
- selected systemd unit files or overrides

Method:
- file existence
- metadata snapshot
- content hash snapshot

Output examples:
- `sensitive_file_hash_changed`
- `ssh_key_added`
- `watched_file_deleted`

---

## 8.3 Listener / exposure monitoring

Goal: detect new listening sockets or important exposure changes.

Signals:
- new TCP/UDP listener
- listener disappeared unexpectedly
- process associated with listener changed

Sources:
- `ss -ltnup`
- `systemctl list-sockets` when useful

Output examples:
- `new_listener`
- `listener_removed`
- `listener_process_changed`

---

## 8.4 systemd / service monitoring

Goal: notice service failures and newly introduced persistence.

Signals:
- service failed
- service newly enabled
- timer newly enabled
- path unit newly enabled
- suspicious unit changes in baseline

Sources:
- `systemctl list-units`
- `systemctl list-unit-files`
- `systemctl list-timers`

Output examples:
- `service_failed`
- `new_enabled_service`
- `new_timer_unit`

---

## 8.5 Cron / scheduled task monitoring

Goal: detect newly introduced scheduled execution paths.

Signals:
- `/etc/crontab` change
- cron.d changes
- user crontab changes (if configured)

Output examples:
- `cron_changed`
- `new_cron_entry`

---

## 9. Event model

Every emitted event should be structured.

Proposed minimum schema:

```json
{
  "id": "uuid-or-deterministic-key",
  "time": "2026-03-21T20:00:00Z",
  "host": "hostname",
  "kind": "new_listener",
  "severity": "warning",
  "source": "listeners.snapshot",
  "summary": "New listening socket detected on 0.0.0.0:9000",
  "details": {
    "address": "0.0.0.0",
    "port": 9000,
    "proto": "tcp",
    "process": "python3",
    "pid": 1234
  },
  "baseline": {...},
  "current": {...},
  "dedupe_key": "new_listener:0.0.0.0:9000:python3"
}
```

### Design rules
- every event must be explainable from source facts
- every event must support deterministic dedupe
- every event should carry enough context for Telegram summary
- every event should be compact enough for LLM summarization

---

## 10. Severity model

Initial severities:

- `info`
- `warning`
- `critical`

### Examples
#### info
- known service restarted cleanly
- previously seen IP login

#### warning
- new listener
- new timer
- failed login burst
- systemd unit drift

#### critical
- change to sudoers
- new authorized key
- root login success
- sensitive file deletion
- suspicious new privileged persistence

Severity should be rule-driven but overrideable by configuration.

---

## 11. LLM/OpenClaw fit

This is the strategic core.

WatchClaw should optimize for three machine-consumption modes:

### A. Direct alerting
Short message suitable for Telegram.

### B. Batch summarization
A digest of all meaningful events over a window.

### C. Explainability
An LLM should be able to answer:
- what changed?
- why does it matter?
- what should the operator do next?

Therefore WatchClaw should prefer:
- semantic events over raw log blobs
- baseline diffs over endless line-by-line dumps
- compact structured payloads over giant log exports

This is why the project should not center itself around massive tool outputs unless they are distilled first.

---

## 12. Integration with OpenClaw

WatchClaw should assume OpenClaw already exists on the host.

### Good roles for OpenClaw
- deliver Telegram alerts
- answer natural language questions about recent events
- summarize security activity
- help re-baseline or explain drift

### Bad roles for OpenClaw
- raw log collector
- sole detection engine
- privileged always-on kernel-level watcher

### Architectural principle
WatchClaw should produce durable structured state locally.
OpenClaw should consume it when needed for communication and interpretation.

---

## 13. Existing tools: stance

## AIDE
Use as optional integrity provider for users who want stronger file integrity checks.
Do not require it for MVP.

## auditd
Use minimally if needed for a few high-value events.
Do not make exhaustive auditd policy the default starting point.

## fail2ban
Treat as a complementary signal and mitigation layer, not as the core product.

## osquery / Wazuh
Do not make them mandatory.
They may later become optional integrations, but not the baseline architecture.

---

## 14. What not to do

### 14.1 Do not start as a giant enterprise product
No fleet manager.
No giant web UI.
No policy engine with 200 toggles.

### 14.2 Do not depend entirely on external heavyweight tools
Otherwise WatchClaw loses identity and becomes glue.

### 14.3 Do not emit too many low-value alerts
Alert fatigue kills trust fast.

### 14.4 Do not hide baseline logic behind opaque abstractions
The user must be able to inspect what “normal” means.

### 14.5 Do not promise automatic remediation in MVP
Detection and explainability first.
Actions later, explicitly.

### 14.6 Do not over-rotate on raw logs
The product should produce observations, not just collect text.

---

## 15. Installation philosophy

Installation should feel like:

- Python package install
- config init
- systemd unit/timer enable
- optional OpenClaw integration enablement

Target shape:

```bash
pip install watchclaw
watchclaw init
sudo watchclaw install-systemd
sudo systemctl enable --now watchclaw.timer
```

This may change, but the principle stands:
- easy to install
- easy to remove
- easy to inspect

---

## 16. MVP recommendation (final)

### Build this first
A Python-based, systemd-timer-driven host observer that:

- reads journal incrementally
- snapshots selected system state
- diffs against a local baseline
- emits compact semantic events
- stores state locally in transparent files
- supports OpenClaw-facing alert consumption

### Specifically include in MVP
- auth/SSH monitoring
- sensitive file hashing
- listener diffing
- systemd/timer drift
- cron drift
- basic severity assignment
- dedupe
- local event log

### Specifically exclude from MVP
- heavy web UI
- full remediation
- mandatory auditd policies
- mandatory Wazuh/osquery
- complicated remote cloud control plane
- deep kernel telemetry

---

## 17. Immediate next engineering step

The next technical artifact should be:

1. a precise config schema
2. a state schema
3. event type definitions
4. the first runnable collector cycle

Recommended build order:

1. config + state model
2. listener snapshot collector
3. sensitive file hash collector
4. journal incremental reader
5. event emitter + JSONL storage
6. severity/dedupe layer
7. OpenClaw alert integration

---

## 18. PM note

As of this draft, the product direction is clear enough to proceed.

If the project stays disciplined, WatchClaw can become:

- a small but very sharp open-source tool
- clearly differentiated from heavyweight security stacks
- genuinely useful in LLM-assisted personal server operations

If the project tries to do everything, it will become noise.

The correct path is:

**compact, legible, baseline-driven host awareness for OpenClaw systems.**
