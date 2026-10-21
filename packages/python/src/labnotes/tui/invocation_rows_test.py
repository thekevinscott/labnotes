from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.tui.invocation_rows import invocation_rows


@pytest.fixture(autouse=True)
def cells() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.tui.invocation_rows.run_cells",
            side_effect=lambda run, columns, nested, live: [
                "run",
                run["id"],
                columns,
                nested,
                live,
            ],
        ) as run_cells,
        mock.patch(
            "labnotes.tui.invocation_rows.group_cells",
            side_effect=lambda group, columns, live: [
                "group",
                group["name"],
                columns,
                live,
            ],
        ) as group_cells,
    ):
        yield {"run_cells": run_cells, "group_cells": group_cells}


def test_lists_runs_when_they_are_not_grouped() -> None:
    experiment = {
        "run_columns": ["id"],
        "runs_live": True,
        "run_groups": None,
        "runs_list": [{"id": "r2"}, {"id": "r1"}],
    }

    assert invocation_rows(experiment, set()) == [
        ("r2", ["run", "r2", ["id"], False, True]),
        ("r1", ["run", "r1", ["id"], False, True]),
    ]


GROUPED = {
    "run_columns": ["id"],
    "runs_live": False,
    "run_groups": [
        {"name": "b", "flat": False, "runs": [{"id": "b/1"}, {"id": "b/2"}]},
        {"name": "lone", "flat": True, "runs": [{"id": "lone"}]},
        {"name": "a", "flat": False, "runs": [{"id": "a/1"}]},
    ],
}


def test_shows_each_invocation_closed() -> None:
    assert invocation_rows(GROUPED, set()) == [
        ("b", ["group", "b", ["id"], False]),
        ("lone", ["run", "lone", ["id"], True, False]),
        ("a", ["group", "a", ["id"], False]),
    ]


def test_lists_the_runs_of_an_open_invocation_under_it() -> None:
    assert invocation_rows(GROUPED, {"b"}) == [
        ("b", ["group", "b", ["id"], False]),
        ("b/1", ["run", "b/1", ["id"], True, False]),
        ("b/2", ["run", "b/2", ["id"], True, False]),
        ("lone", ["run", "lone", ["id"], True, False]),
        ("a", ["group", "a", ["id"], False]),
    ]
