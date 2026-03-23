# WatchClaw Tasks

Status: active working list
Owner: JC (PM)
Maintainer: Sedna

## Guiding principles

Every task should be evaluated through:
- **Trazabilidad** — every alert and decision should be explainable
- **Ease of mind** — low noise, predictable behavior, calm operator experience
- **Simpleza** — minimal moving parts, understandable install and runtime model

---

## Current focus

Refine the project definition before deep implementation.

### Goal of current phase

Turn the initial technical direction into a smaller, sharper MVP that is:
- easier to install
- easier to reason about
- easier to trust
- easier to explain to users and contributors

---

## Phase 1 — Document iteration

### P1. Re-read living technical document
- [ ] Review `docs/LIVING-TECHNICAL-DOCUMENT.md` end-to-end
- [ ] Mark sections that feel too broad, heavy, or premature
- [ ] Mark sections that are not directly serving the MVP

### P2. Tighten for trazabilidad
- [ ] Ensure baseline/state logic is explicit and inspectable
- [ ] Ensure every proposed event type is explainable from source facts
- [ ] Ensure alert reasoning can be reconstructed from local state
- [ ] Add a short section describing "why did this alert happen?"

### P3. Tighten for ease of mind
- [ ] Reduce anything that would likely create alert fatigue
- [ ] Clarify defaults that should be quiet and safe
- [ ] Add guidance for severity thresholds and deduplication
- [ ] Add operator experience principles for alert wording

### P4. Tighten for simpleza
- [ ] Remove any design element that smells like premature SIEM complexity
- [ ] Prefer timer-based execution over daemon complexity unless proven needed
- [ ] Keep storage simple and inspectable in MVP
- [ ] Limit MVP integrations to the minimum useful set

### P5. Commit iteration
- [ ] Update `docs/LIVING-TECHNICAL-DOCUMENT.md`
- [ ] Commit with a message focused on refinement
- [ ] Push changes to GitHub

---

## Phase 2 — Product shape

### P6. Write MVP definition document
- [ ] Create `docs/MVP.md`
- [ ] Define exact MVP goals
- [ ] Define exact non-goals
- [ ] Define the first supported detections
- [ ] Define success criteria for first release

### P7. Define alert philosophy
- [ ] Create `docs/ALERTING.md`
- [ ] Define info / warning / critical
- [ ] Define what should page immediately vs wait for digest
- [ ] Define anti-noise rules
- [ ] Define what "ease of mind" means operationally

### P8. Define install philosophy
- [ ] Create `docs/INSTALLATION.md`
- [ ] Define assumptions about existing OpenClaw host
- [ ] Define systemd model
- [ ] Define config and state paths
- [ ] Define uninstall / rollback expectations

---

## Phase 3 — Technical schemas

### P9. Define config schema
- [ ] Create `docs/CONFIG-SCHEMA.md`
- [ ] Define watched paths
- [ ] Define enable/disable flags for sensors
- [ ] Define alert routing options
- [ ] Define dedupe and baseline options

### P10. Define state schema
- [ ] Create `docs/STATE-SCHEMA.md`
- [ ] Define state file layout
- [ ] Define journal cursor storage
- [ ] Define baseline structure
- [ ] Define event log layout

### P11. Define event model
- [ ] Create `docs/EVENT-MODEL.md`
- [ ] Define event schema
- [ ] Define dedupe keys
- [ ] Define severity mapping
- [ ] Define examples for core event types

---

## Phase 4 — First implementation slice

### P12. Bootstrap Python package properly
- [ ] Confirm package naming is consistent (`watchclaw`)
- [ ] Add CLI subcommands scaffold
- [ ] Add basic project structure for collectors, state, events, alerts

### P13. Implement first collector: listeners
- [ ] Snapshot `ss -ltnup`
- [ ] Normalize listeners into stable records
- [ ] Compare against baseline
- [ ] Emit `new_listener` / `listener_removed`

### P14. Implement first collector: sensitive file hashes
- [ ] Hash configured files
- [ ] Detect new / changed / deleted
- [ ] Emit semantic events

### P15. Implement first collector: journal incremental reader
- [ ] Persist journal cursor
- [ ] Read auth-related entries incrementally
- [ ] Extract SSH success/failure signals
- [ ] Emit normalized events

### P16. Implement local event store
- [ ] Write events as JSONL
- [ ] Keep format human-readable
- [ ] Add simple retention strategy later if needed

---

## Phase 5 — OpenClaw-facing layer

### P17. Define alert transport strategy
- [ ] Decide local file handoff vs direct OpenClaw messaging
- [ ] Prefer durable local-first path
- [ ] Document tradeoffs

### P18. Design OpenClaw integration
- [ ] Decide if a WatchClaw skill is needed in MVP or later
- [ ] Define natural-language query use cases
- [ ] Define summary/report flows

---

## Immediate next actions

### Next up
- [ ] Re-iterate the living technical document from trazabilidad / ease of mind / simpleza
- [ ] Push revised version
- [ ] Then create `docs/MVP.md`

---

## Notes

This file should stay current.
If priorities change, update this before expanding implementation.
