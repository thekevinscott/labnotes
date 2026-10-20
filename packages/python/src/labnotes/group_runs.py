from collections.abc import Mapping, Sequence

from labnotes.invocation_started import invocation_started


def shared_params(
    runs: list[dict[str, object]], params: Sequence[str]
) -> dict[str, object]:
    return {
        key: runs[0][key]
        for key in params
        if all(run[key] == runs[0][key] for run in runs)
    }


def group_runs(
    runs: list[dict[str, object]],
    params: Sequence[str],
    totals: Mapping[str, int],
) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for run in runs:
        groups.setdefault(str(run["id"]).partition("/")[0], []).append(run)
    return [
        {
            "name": name,
            "started": invocation_started(name),
            "runs": members,
            "total": totals.get(name, len(members)),
            "shared": shared_params(members, params),
            "passed": sum(1 for run in members if run["labnotes_completed"]),
            "failed": sum(1 for run in members if not run["labnotes_completed"]),
        }
        for name, members in sorted(groups.items(), reverse=True)
    ]
