# Architecture Notes

Planned components:

- local Python watcher service
- baseline/state store
- event detectors for ssh auth / files / listeners
- incremental auth reader with journal-first, logfile-fallback behavior
- inline delivery-preparation layer that turns fresh events into transport-ready notifications during the same run
- alert transport / acknowledgement layer
- OpenClaw-facing integration layer
- install flow for existing OpenClaw hosts
