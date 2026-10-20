from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.group_runs import group_runs


@pytest.fixture(autouse=True)
def invocation_started() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.group_runs.invocation_started", side_effect=lambda name: f"<{name}>"
    ) as started:
        yield started


def test_groups_runs_by_invocation_newest_first_keeping_their_order() -> None:
    runs: list[dict[str, object]] = [
        {"id": "20261019-a/x", "labnotes_completed": 1},
        {"id": "20261020-b/z", "labnotes_completed": 0},
        {"id": "20261019-a/y", "labnotes_completed": 0},
        {"id": "20261020-b/w", "labnotes_completed": 1},
    ]

    assert group_runs(runs, [], {"20261020-b": 5, "20261019-a": 2}) == [
        {
            "name": "20261020-b",
            "started": "<20261020-b>",
            "runs": [runs[1], runs[3]],
            "total": 5,
            "shared": {},
            "passed": 1,
            "failed": 1,
        },
        {
            "name": "20261019-a",
            "started": "<20261019-a>",
            "runs": [runs[0], runs[2]],
            "total": 2,
            "shared": {},
            "passed": 1,
            "failed": 1,
        },
    ]


def test_counts_passed_and_failed_runs() -> None:
    runs: list[dict[str, object]] = [
        {"id": "a/x", "labnotes_completed": 1},
        {"id": "a/y", "labnotes_completed": 1},
        {"id": "a/z", "labnotes_completed": 0},
    ]

    [group] = group_runs(runs, [], {"a": 3})

    assert (group["passed"], group["failed"]) == (2, 1)


def test_falls_back_to_the_shown_runs_without_a_total() -> None:
    [group] = group_runs([{"id": "a/x", "labnotes_completed": 1}], [], {})

    assert group["total"] == 1


def test_keeps_the_params_its_runs_share() -> None:
    runs: list[dict[str, object]] = [
        {"id": "a/x", "labnotes_completed": 1, "m": "a", "k": 1, "j": None},
        {"id": "a/y", "labnotes_completed": 1, "m": "b", "k": 1, "j": None},
    ]

    [group] = group_runs(runs, ["m", "k", "j"], {})

    assert group["shared"] == {"k": 1, "j": None}


def test_puts_a_run_without_an_invocation_in_its_own_group() -> None:
    [group] = group_runs([{"id": "lone", "labnotes_completed": 0}], [], {"lone": 1})

    assert (group["name"], group["passed"], group["failed"]) == ("lone", 0, 1)
