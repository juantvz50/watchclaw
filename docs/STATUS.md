# Status

## 2026-03-23

Refined `docs/LIVING-TECHNICAL-DOCUMENT.md` to make the MVP calmer and narrower.

What changed:
- centered the document on three operating lenses: trazabilidad, ease of mind, simpleza
- tightened the MVP around a timer-based local observer with transparent state
- made baseline behavior and re-baselining explicit
- added a concrete "why did this alert happen?" contract for explainability
- clarified noise-control, severity, and OpenClaw's role as consumer rather than source of truth
- reduced pressure toward heavyweight integrations and premature platform scope

Next concrete engineering step:
- define the config/state/event contracts and implement the first runnable listener collector slice (`ss` snapshot -> baseline diff -> `new_listener` / `listener_removed` -> JSONL event storage -> basic explain path)
