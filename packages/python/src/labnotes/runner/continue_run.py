from labnotes.runner.first_invocation import first_invocation

# Per-invocation keys that a later invocation may leave unset.
UNSET = {"args", "meta", "pid", "pid_created", "retry_of"}


def continue_run(
    previous: dict[str, object], run: dict[str, object], invocation: dict[str, object]
) -> dict[str, object]:
    invocations = previous.get("invocations")
    if not isinstance(invocations, list):
        invocations = [] if not previous else [first_invocation(previous)]
    kept = {key: value for key, value in previous.items() if key not in UNSET}
    return (
        kept
        | run
        | {
            "created": previous.get("created", run["created"]),
            "invocations": [*invocations, invocation],
        }
    )
