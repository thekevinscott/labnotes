from collections.abc import Mapping, Sequence

from labnotes.invocation_started import invocation_started
from labnotes.shared_params import shared_params


def group_runs(
    runs: list[dict[str, object]],
    params: Sequence[str],
    totals: Mapping[str, int],
) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {}
    flat: set[str] = set()
    for run in runs:
        name, nested, _ = str(run["id"]).partition("/")
        groups.setdefault(name, []).append(run)
        if not nested:
            flat.add(name)
    return [
        {
            "name": name,
            "flat": name in flat,
            "started": invocation_started(name),
            "runs": members,
            "total": totals.get(name, len(members)),
            "shared": shared_params(members, params),
            "passed": sum(1 for run in members if run["labnotes_completed"]),
            "failed": sum(1 for run in members if not run["labnotes_completed"]),
        }
        for name, members in sorted(groups.items(), reverse=True)
    ]
