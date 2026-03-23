# WatchClaw — Living Technical Document

## Status

Draft v0.2
Owner: JC (Project Manager)
Technical counterpart: Sedna
Project type: Open-source host watchdog for systems already running OpenClaw

---

## 1. Purpose

WatchClaw exists to give a Linux operator a **calm, inspectable view of important host changes**.

It should be:

- lightweight
- explainable
- easy to install on an existing OpenClaw host
- quiet by default
- readable by both humans and LLMs

The product is not "security tooling in general".
It is a **local baseline + diff + semantic event layer** for host state.

Core promise:

> WatchClaw should let an operator answer, with low stress: what changed, why it matters, and whether action is needed.

---

## 2. Product thesis

Most host security tooling is strong at raw collection, policy enforcement, or both.
What is often missing on a personal server or small host is:

- a small install surface
- a readable model of normal state
- compact explanations of drift
- predictable alerting behavior
- outputs that are easy to hand to OpenClaw or an LLM for summary

WatchClaw should therefore be designed as:

> a trustable host change observer for OpenClaw systems

Not as:

- a SIEM clone
- a full HIDS replacement
- an enterprise compliance platform
- a magical auto-remediator

---

## 3. Primary design constraints

Everything should be evaluated through these lenses.

### 3.1 Trazabilidad

Every alert must be reconstructible from local facts.

A user should be able to inspect:

- what WatchClaw watched
- the previous baseline
- the current observation
- the rule that turned a diff into an event
- whether the event was deduped, suppressed, or escalated

No opaque "AI said this looks bad" logic in the MVP.
LLMs may summarize events later, but they should not be the origin of truth.

### 3.2 Ease of mind

The operator experience should feel calm.

That means:

- quiet defaults
- a small number of well-defined sensors
- severity that matches actual operator urgency
- repeat events deduped instead of spammed
- installation and uninstall that do not feel risky

The product should reduce background anxiety, not create more of it.

### 3.3 Simpleza

The MVP should use the fewest moving parts that can still deliver value.

Prefer:

- timer-based execution over daemon complexity
- local files over database complexity
- semantic events over raw log shipping
- a small trusted surface over broad feature coverage

---

## 4. Install contract

The MVP assumes the target machine already has:

- Linux
- Python available or installable
- systemd
- OpenClaw already running
- intermittent outbound network access at most

WatchClaw should still be useful if OpenClaw delivery fails.
Local collection and local state are the primary contract.
Remote alerting is secondary.

Installation should feel reversible and low-risk:

1. install package
2. initialize config and state paths
3. enable a `systemd` timer
4. inspect what it is watching

Uninstall should leave the host in a legible state with no hidden components.

---

## 5. Non-goals

For the MVP, WatchClaw is **not** trying to be:

- Wazuh replacement
- osquery replacement
- auditd replacement
- EDR/XDR platform
- incident response suite
- hardening framework
- active network IDS
- malware scanner
- remote fleet manager
- enterprise dashboard
- cloud control plane
- automatic remediation system

Also out of scope for MVP:

- policy enforcement
- deep kernel telemetry
- mandatory heavyweight integrations
- high-frequency streaming pipelines
- broad compliance mapping

If a feature increases install burden, noise, or conceptual sprawl without clearly improving trust, it should wait.

---

## 6. Architectural position

WatchClaw should sit between native host truth and operator-facing explanation.

### Layer A — System truth

Native interfaces and standard tools, such as:

- `journalctl`
- auth logs / journald auth units
- `ss`
- `systemctl`
- cron data
- selected files in `/etc` and SSH locations

Optional later providers may include:

- AIDE
- minimal auditd signals
- fail2ban state

These are inputs, not product identity.

### Layer B — Collection and normalization

WatchClaw gathers a small set of observations:

- snapshots
- incremental journal reads
- selected file integrity state
- selected scheduler and service state

Then it normalizes them into deterministic records.

### Layer C — Baseline and diff

WatchClaw compares current observation against stored baseline and emits semantic events such as:

- `new_listener`
- `service_failed`
- `ssh_login_new_ip`
- `ssh_key_added`
- `sensitive_file_hash_changed`
- `new_timer_unit`

### Layer D — Routing and explanation

Events can then be:

- deduped
- grouped
- severity-mapped
- summarized
- handed to OpenClaw

### Layer E — Human / LLM consumption

Final output must be compact, explainable, and digest-friendly.

---

## 7. MVP shape

### 7.1 Runtime model

The MVP should use a **periodic runner via `systemd` timer**.

Why this is the right default:

- easier to trust
- easier to debug
- easier to uninstall
- naturally aligned with snapshot + diff logic
- avoids daemon lifecycle complexity

A permanent daemon is not justified until the timer model clearly fails operationally.

### 7.2 Language

Primary language: **Python**

Why:

- fastest implementation path
- easy subprocess integration with Linux tools
- easy JSON/JSONL handling
- simple packaging for existing hosts
- enough performance for MVP scope

The main problem is signal modeling and explainable state, not raw throughput.

### 7.3 Storage model

Use transparent local files first.

Suggested layout:

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

Principles:

- state must be human-inspectable
- event history must be append-friendly
- journal cursor must be explicit
- dedupe state must be explicit
- no opaque binary state in MVP

SQLite may be reasonable later, but only after the data model is proven.

---

## 8. MVP sensors

The MVP should stay narrow. The goal is confidence, not coverage theater.

### 8.1 SSH / auth monitoring

Goal: detect meaningful remote access activity.

Signals:

- successful SSH login
- failed SSH burst
- login from IP not seen before
- invalid user attempts
- root login attempts or success
- selected sudo usage signals

Outputs:

- `ssh_login_success`
- `ssh_login_new_ip`
- `ssh_failed_burst`
- `ssh_invalid_user_attempt`
- `root_login_attempt`

### 8.2 Sensitive file integrity

Goal: notice changes to high-value local trust boundaries.

Initial watched paths:

- `/etc/ssh/sshd_config`
- `/etc/passwd`
- `/etc/group`
- `/etc/sudoers`
- `/etc/crontab`
- `/root/.ssh/authorized_keys`
- selected user `authorized_keys`
- selected systemd unit files or overrides

Method:

- existence check
- metadata snapshot
- content hash snapshot

Outputs:

- `sensitive_file_hash_changed`
- `ssh_key_added`
- `watched_file_deleted`

### 8.3 Listener / exposure monitoring

Goal: detect new or removed listening sockets.

Signals:

- new TCP/UDP listener
- listener removed
- process for listener changed

Source:

- `ss -ltnup`

Outputs:

- `new_listener`
- `listener_removed`
- `listener_process_changed`

### 8.4 systemd / persistence monitoring

Goal: notice failures and new persistence paths.

Signals:

- service failed
- service newly enabled
- timer newly enabled
- path unit newly enabled
- suspicious unit drift

Sources:

- `systemctl list-units`
- `systemctl list-unit-files`
- `systemctl list-timers`

Outputs:

- `service_failed`
- `new_enabled_service`
- `new_timer_unit`

### 8.5 Cron / scheduled task monitoring

Goal: detect newly introduced scheduled execution.

Signals:

- `/etc/crontab` changed
- `cron.d` changed
- selected user crontabs changed, if configured

Outputs:

- `cron_changed`
- `new_cron_entry`

---

## 9. Deliberate exclusions from the MVP

Even if tempting, do not add these to the first release:

- auditd policy complexity as a default requirement
- AIDE as a required dependency
- multi-host management
- web dashboard
- auto-remediation
- remote command execution
- high-volume raw log export
- probabilistic ML detection layers

WatchClaw earns trust by being inspectable first.
Breadth can come later.

---

## 10. Baseline model

The baseline is a first-class product surface.

Rules:

- baseline files must be readable by an operator
- baseline creation must be explicit
- baseline rebuild must be explicit
- WatchClaw must distinguish between "first observation" and "drift from known state"
- re-baselining should be a conscious operator action, not a silent side effect

### Baseline lifecycle

1. first run records initial known-good state
2. future runs compare current state against that baseline
3. meaningful differences emit semantic events
4. operator can review drift
5. operator may intentionally accept new normal via re-baseline

The system must never make the operator wonder whether a change was silently absorbed.

---

## 11. Why did this alert happen?

Every event should answer this question directly.

Minimum explanation contract for an alert:

- **what was observed now**
- **what was previously known**
- **what rule matched**
- **why severity was assigned**
- **whether this is new or repeated**

Example shape:

```json
{
  "kind": "new_listener",
  "summary": "New listening socket detected on 0.0.0.0:9000",
  "why": {
    "observed": "0.0.0.0:9000/tcp owned by python3 pid 1234",
    "baseline": "port not present in previous listener baseline",
    "rule": "emit new_listener when current listener key is absent from prior baseline",
    "severity_reason": "warning because new network exposure exists",
    "dedupe": "first occurrence in current dedupe window"
  }
}
```

If an operator cannot reconstruct the event from local state, the design is wrong.

---

## 12. Event model

Every emitted event should be structured and compact.

Minimum schema:

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
  "baseline": {},
  "current": {},
  "why": {},
  "dedupe_key": "new_listener:0.0.0.0:9000:python3"
}
```

Design rules:

- every event must be explainable from source facts
- every event must support deterministic dedupe
- every event should fit Telegram-sized summary generation
- every event should be compact enough for batch LLM summarization

---

## 13. Severity and noise model

Initial severities:

- `info`
- `warning`
- `critical`

### Severity examples

#### info

- known service restart
- SSH login from known IP
- non-sensitive watched file metadata drift with no content change

#### warning

- new listener
- new timer
- failed login burst
- systemd drift
- cron drift

#### critical

- change to `sudoers`
- new authorized key
- root login success
- sensitive file deletion
- suspicious new privileged persistence

### Noise-control rules

- dedupe repeated identical events within a configurable window
- default to digest for `info`
- avoid paging on every failed login line; aggregate bursts
- do not emit events for source noise that cannot be explained clearly
- prefer one good alert over ten raw ones

Ease of mind matters as much as detection quality.
A noisy system is a system that stops being trusted.

---

## 14. OpenClaw integration

OpenClaw is an integration surface, not the local source of truth.

### Good roles for OpenClaw

- deliver alerts
- produce a daily or hourly digest
- answer natural-language questions about recent events
- help explain drift to the operator

### Bad roles for OpenClaw

- raw log sink
- primary detection engine
- privileged always-on host observer

Architectural rule:

> WatchClaw owns local truth. OpenClaw consumes WatchClaw output for communication and interpretation.

This keeps the host behavior understandable even if messaging or LLM layers fail.

---

## 15. Installation philosophy

Installation should feel boring in the best way.

Target operator flow:

```bash
pip install watchclaw
watchclaw init
sudo watchclaw install-systemd
sudo systemctl enable --now watchclaw.timer
watchclaw status
watchclaw explain-baseline
```

Principles:

- easy to install
- easy to remove
- easy to inspect
- easy to confirm what is active

The first install experience should answer three questions quickly:

- where is state stored?
- what is being watched?
- how often does it run?

---

## 16. MVP recommendation

Build this first:

A Python-based, `systemd`-timer-driven host observer that:

- reads journal incrementally
- snapshots selected host state
- diffs against explicit local baselines
- emits compact semantic events
- stores all state locally in transparent files
- lets OpenClaw consume alerts without making OpenClaw mandatory for core function

### Include in MVP

- auth / SSH monitoring
- sensitive file hashing
- listener diffing
- systemd and timer drift
- cron drift
- severity mapping
- dedupe
- local event log
- explicit explainability fields for each event

### Exclude from MVP

- daemon-first runtime
- heavy UI
- mandatory auditd policies
- mandatory Wazuh/osquery/AIDE
- auto-remediation
- fleet control plane
- deep kernel telemetry

---

## 17. Immediate next engineering step

The next technical artifact should not be broad implementation.
It should be the **contract surface** for the first runnable slice.

Build order:

1. config schema
2. state schema
3. event type definitions
4. one runnable collector cycle

Recommended first runnable slice:

1. listener snapshot collector
2. explicit baseline file for listeners
3. `new_listener` / `listener_removed` event emission
4. JSONL event store
5. minimal `watchclaw explain <event-id>` path

Why this slice first:

- easy to verify locally
- easy to explain
- immediately tests baseline, diff, event, and dedupe design
- low install and debugging complexity

---

## 18. Final product stance

If WatchClaw stays disciplined, it can become:

- a small but sharp open-source tool
- easier to trust than heavyweight stacks for personal hosts
- a strong substrate for OpenClaw-assisted security review

If it expands too early, it will become noisy and vague.

The correct direction is:

**compact, legible, baseline-driven host awareness for OpenClaw systems, with explicit reasoning and calm defaults.**
