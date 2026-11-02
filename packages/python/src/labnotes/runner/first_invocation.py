def first_invocation(run: dict[str, object]) -> dict[str, object]:
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
