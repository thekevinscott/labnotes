from labnotes.invocation_started import invocation_started


def group_runs(runs: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for run in runs:
        groups.setdefault(str(run["id"]).partition("/")[0], []).append(run)
    return [
        {
            "name": name,
            "started": invocation_started(name),
            "runs": members,
            "passed": sum(1 for run in members if run["labnotes_completed"]),
            "failed": sum(1 for run in members if not run["labnotes_completed"]),
        }
        for name, members in sorted(groups.items(), reverse=True)
    ]
