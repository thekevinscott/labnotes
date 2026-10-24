from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest

from labnotes.tui.invocation_rows import invocation_rows

COLUMNS = [{"key": "id", "label": "Run"}]


@pytest.fixture(autouse=True)
def cells() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.tui.invocation_rows.run_cells",
            side_effect=lambda row, columns, nested, live: [
                "run",
                row,
                columns,
                nested,
                live,
            ],
        ) as run_cells,
        mock.patch(
            "labnotes.tui.invocation_rows.group_cells",
            side_effect=lambda group, columns, live, opened: [
                "group",
                group["name"],
                columns,
                live,
                opened,
            ],
        ) as group_cells,
    ):
        yield {"run_cells": run_cells, "group_cells": group_cells}


def run(id: str) -> dict[str, str]:
    return {"id": id, "folder": f"runs/{id}"}


def rows(*ids: str) -> dict[str, Any]:
    return {f"runs/{id}": f"row {id}" for id in ids}


def test_lists_runs_when_they_are_not_grouped() -> None:
    experiment = {
        "runs_live": True,
        "run_groups": None,
        "runs_list": [run("r2"), run("r1")],
    }

    assert invocation_rows(experiment, set(), COLUMNS, rows("r1", "r2")) == [
        ("r2", ["run", "row r2", COLUMNS, False, True]),
        ("r1", ["run", "row r1", COLUMNS, False, True]),
    ]


GROUPED = {
    "runs_live": False,
    "run_groups": [
        {"name": "b", "flat": False, "runs": [run("b/1"), run("b/2")]},
        {"name": "lone", "flat": True, "runs": [run("lone")]},
        {"name": "a", "flat": False, "runs": [run("a/1")]},
    ],
}
ALL = rows("b/1", "b/2", "lone", "a/1")


def test_shows_each_invocation_closed() -> None:
    assert invocation_rows(GROUPED, set(), COLUMNS, ALL) == [
        ("b", ["group", "b", COLUMNS, False, False]),
        ("lone", ["run", "row lone", COLUMNS, True, False]),
        ("a", ["group", "a", COLUMNS, False, False]),
    ]


def test_lists_the_runs_of_an_open_invocation_under_it() -> None:
    assert invocation_rows(GROUPED, {"b"}, COLUMNS, ALL) == [
        ("b", ["group", "b", COLUMNS, False, True]),
        ("b/1", ["run", "row b/1", COLUMNS, True, False]),
        ("b/2", ["run", "row b/2", COLUMNS, True, False]),
        ("lone", ["run", "row lone", COLUMNS, True, False]),
        ("a", ["group", "a", COLUMNS, False, False]),
    ]
