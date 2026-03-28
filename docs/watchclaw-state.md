# WatchClaw State

## Goal

Build WatchClaw into an open-source, installable host watchdog for systems already running OpenClaw.

## Success criteria

- The project has a small, defensible MVP.
- The MVP is installable on an existing Linux + OpenClaw host.
- Core behavior is explainable and low-noise.
- The first runnable slice exists with tests.
- Progress is recoverable from project files, not chat memory.

## Core values

- **Traceability**
- **Peace of mind**
- **Simplicity**

## Current status

`complete`

## Current step

Extend the Telegram layer into a practical local-first delivery bridge:
- durable delivery state
- notification-worthiness defaults
- prepare/ack CLI flow
- tests and docs

## Completed work

- Project repo created and published.
- Initial technical direction documented.
- Tooling research completed.
- Living technical document iterated and narrowed.
- Status doc added.
- Long-task coordination skill installed for process discipline.
- MVP detection slices implemented for listeners, watched files, and SSH/auth.
- Telegram-ready rendering layer implemented.
- Telegram delivery-preparation slice implemented with durable local delivery state, prepare/ack CLI commands, tests, and docs.

## Next action

Thin remaining integration option:
1. have OpenClaw call `prepare-telegram-delivery`
2. send each returned `payload` through its Telegram channel adapter
3. call `ack-telegram-delivery --batch-id ... --status sent|failed`

No repo-side blocker remains for that handoff.

## Blockers

None right now.

## Active owner

- Sedna — coordinator / implementation
- JC — PM / approval on meaningful decisions

## Pending decisions from JC

- None active at this exact step.
- Next likely decision: whether the lightweight per-service research profile layer enters immediately after core detectors or waits until after auth/file slices.

## Next checkpoint

After the three contract docs are drafted, stop and ping JC before implementation continues.
