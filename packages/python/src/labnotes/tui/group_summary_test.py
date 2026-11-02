from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.tui.group_summary import Group, group_summary

RUNS = [
    {"id": "inv/a", "status": "passed", "m": 1},
    {"id": "inv/b", "status": "failed", "m": 2},
    {"id": "inv/c", "status": "unfinished", "m": 1},
    {"id": "inv/d", "status": "passed", "m": 1},
]


@pytest.fixture(autouse=True)
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.tui.group_summary.invocation_started", return_value="when"
        ) as invocation_started,
        mock.patch(
            "labnotes.tui.group_summary.shared_params", return_value={"n": 3}
        ) as shared_params,
    ):
        yield {
            "invocation_started": invocation_started,
            "shared_params": shared_params,
        }


def test_counts_the_runs_by_status_and_finds_what_they_share(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    group = Group("inv", ("a", "b", "c", "d"), False)

    assert group_summary(group, RUNS, ["m", "n"]) == {
        "name": "inv",
        "runs": RUNS,
        "started": "when",
        "shared": {"n": 3},
        "passed": 2,
        "failed": 1,
        "unfinished": 1,
    }
    collaborators["invocation_started"].assert_called_once_with("inv")
    collaborators["shared_params"].assert_called_once_with(RUNS, ["m", "n"])
