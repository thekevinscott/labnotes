from collections.abc import Mapping, Sequence
from typing import Any

from labnotes.invocation_started import invocation_started
from labnotes.shared_params import shared_params
from labnotes.view.group import Group


def group_summary(
    group: Group, runs: Sequence[Mapping[str, Any]], params: Sequence[str]
) -> dict[str, Any]:
    statuses = [run["status"] for run in runs]
    return {
        "name": group.name,
        "runs": list(runs),
        "started": invocation_started(group.name),
        "shared": shared_params([dict(run) for run in runs], params),
        "passed": statuses.count("passed"),
        "failed": statuses.count("failed"),
        "unfinished": statuses.count("unfinished"),
    }
