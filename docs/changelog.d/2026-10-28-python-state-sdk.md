Added `labnotes.set_state({...})` and `labnotes.get_state()` for passing JSON
state from setup to teardown. Writes merge by key. State lives in the
invocation folder, or in a temporary file through teardown when several matrix
runs have no shared folder. Both functions raise outside hooks; run commands
do not receive the state context, and nested invocations use their own context.
