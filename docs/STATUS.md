# Status

## 2026-03-23

Refined `docs/LIVING-TECHNICAL-DOCUMENT.md` to make the MVP calmer and narrower.

What changed:
- centered the document on three operating lenses: Traceability, Peace of mind, Simplicity
- tightened the MVP around a timer-based local observer with transparent state
- made baseline behavior and re-baselining explicit
- added a concrete "why did this alert happen?" contract for explainability
- clarified noise-control, severity, and OpenClaw's role as consumer rather than source of truth
- reduced pressure toward heavyweight integrations and premature platform scope

Next concrete engineering step:
- tighten the new SSH/auth journal slice around real-host validation, especially journald permission behavior and burst tuning, without widening the config surface prematurely

## 2026-03-23 — auth slice

Implemented a narrow SSH/auth monitoring slice:
- journal-first incremental reads using persisted `journalctl` cursor state
- honest logfile fallback for `/var/log/auth.log` and `/var/log/secure`
- normalized high-value SSH events: `ssh_login_success`, `ssh_invalid_user`, `ssh_failed_login_burst`
- state/schema/docs updates to keep the slice inspectable and explainable

## 2026-03-28 — reactive delivery prep slice

Implemented a smaller, more reactive event -> delivery path:
- added inline Telegram delivery preparation during `watchclaw run-once`
- kept the durable `prepared` / `sent` / `failed` / `skipped` state model intact
- preserved `prepare-telegram-delivery` as a recovery/backfill path instead of the only preparation path
- added config control via `runtime.delivery.telegram_inline`
- extended tests/docs around the new behavior

## Design note

A future enrichment layer should support lightweight per-service research saved as local markdown profiles (for example under a local services directory). This should stay optional and must not become a runtime dependency of core detection.
