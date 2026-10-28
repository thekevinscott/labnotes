# Run commands can read invocation state

Run commands can now call `labnotes.get_state()` to read what setup saved,
including queued runs and retries. `set_state()` raises in runs, keeping state
writable only in setup and teardown. `meta` still has no state, and nested
invocations use their own state context.
