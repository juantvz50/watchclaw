# Architecture Notes

Planned components:

- local Python watcher service
- baseline/state store
- event detectors for ssh auth / files / listeners
- incremental auth reader with journal-first, logfile-fallback behavior
- alert transport layer
- OpenClaw-facing integration layer
- install flow for existing OpenClaw hosts
