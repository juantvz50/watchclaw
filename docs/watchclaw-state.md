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

`running`

## Current step

Define the durable contracts for the MVP:
- config
- local state
- event model

## Completed work

- Project repo created and published.
- Initial technical direction documented.
- Tooling research completed.
- Living technical document iterated and narrowed.
- Status doc added.
- Long-task coordination skill installed for process discipline.

## Next action

Create the first contract docs:
1. `docs/CONFIG-SCHEMA.md`
2. `docs/STATE-SCHEMA.md`
3. `docs/EVENT-MODEL.md`

Then use them to implement the first runnable slice:
- `ss` snapshot
- baseline diff
- `new_listener` / `listener_removed`
- JSONL event storage
- basic explain path

## Blockers

None right now.

## Active owner

- Sedna — coordinator / implementation
- JC — PM / approval on meaningful decisions

## Pending decisions from JC

- None active at this exact step.
- Next likely decision: JSON/JSONL-only MVP vs introducing SQLite early.

## Next checkpoint

After the three contract docs are drafted, stop and ping JC before implementation continues.
