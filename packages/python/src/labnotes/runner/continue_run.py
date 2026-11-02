# Per-invocation keys that a later invocation may leave unset.
UNSET = {"args", "meta", "pid", "pid_created", "retry_of"}


def continue_run(
    previous: dict[str, object], run: dict[str, object], invocation: dict[str, object]
) -> dict[str, object]:
    invocations = previous.get("invocations")
    if not isinstance(invocations, list):
        invocations = [] if not previous else [_first_invocation(previous)]
    kept = {key: value for key, value in previous.items() if key not in UNSET}
    return (
        kept
        | run
        | {
            "created": previous.get("created", run["created"]),
            "invocations": [*invocations, invocation],
        }
    )


def _first_invocation(run: dict[str, object]) -> dict[str, object]:
    git = run.get("git")
    return {
        "started": run.get("created"),
        "ended": run.get("ended"),
        "exit_code": run.get("exit_code"),
        "ended_by": run.get("ended_by"),
        "error": run.get("error"),
        "git": git.get("commit") if isinstance(git, dict) else None,
        "args": run.get("args", []),
        "stdout": "stdout.log",
        "stderr": "stderr.log",
    }
