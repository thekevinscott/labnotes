from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.tui.invocation_rows import Experiment, invocation_rows
from labnotes.view.group import Group

COLUMNS = [{"key": "id", "label": "Run"}]
CONFIG = {"params": {"m": [1, 2]}}


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
                group,
                columns,
                live,
                opened,
            ],
        ) as group_cells,
        mock.patch(
            "labnotes.tui.invocation_rows.group_summary",
            side_effect=lambda group, runs, params: (group.name, runs, params),
        ) as group_summary,
        mock.patch(
            "labnotes.tui.invocation_rows.param_names", return_value=["m"]
        ) as param_names,
    ):
        yield {
            "run_cells": run_cells,
            "group_cells": group_cells,
            "group_summary": group_summary,
            "param_names": param_names,
        }


def runs(*ids: str) -> dict[str, dict[str, str]]:
    return {f"runs/{id}": {"id": id} for id in ids}


def rows(*ids: str) -> dict[str, Any]:
    return {f"runs/{id}": f"row {id}" for id in ids}


def test_lists_runs_in_order_when_they_are_not_grouped() -> None:
    experiment = Experiment(Path("/p"), "alpha", runs("r2", "r1"), live=True)

    assert invocation_rows(experiment, set(), COLUMNS, rows("r1", "r2")) == [
        ("r2", ["run", "row r2", COLUMNS, False, True]),
        ("r1", ["run", "row r1", COLUMNS, False, True]),
    ]


GROUPS = (
    Group("b", ("runs/b/1", "runs/b/2"), False),
    Group("lone", ("runs/lone",), True),
    Group("a", ("runs/a/1",), False),
)
GROUPED = Experiment(
    Path("/p"), "alpha", runs("b/1", "b/2", "lone", "a/1"), CONFIG, groups=GROUPS
)
ALL = rows("b/1", "b/2", "lone", "a/1")
B = ("b", [{"id": "b/1"}, {"id": "b/2"}], ["m"])
A = ("a", [{"id": "a/1"}], ["m"])


def test_shows_each_invocation_closed_with_its_summary(
    cells: dict[str, mock.MagicMock],
) -> None:
    assert invocation_rows(GROUPED, set(), COLUMNS, ALL) == [
        ("b", ["group", B, COLUMNS, False, False]),
        ("lone", ["run", "row lone", COLUMNS, True, False]),
        ("a", ["group", A, COLUMNS, False, False]),
    ]
    cells["param_names"].assert_called_once_with(CONFIG)


def test_lists_the_runs_of_an_open_invocation_under_it() -> None:
    assert invocation_rows(GROUPED, {"b"}, COLUMNS, ALL) == [
        ("b", ["group", B, COLUMNS, False, True]),
        ("b/1", ["run", "row b/1", COLUMNS, True, False]),
        ("b/2", ["run", "row b/2", COLUMNS, True, False]),
        ("lone", ["run", "row lone", COLUMNS, True, False]),
        ("a", ["group", A, COLUMNS, False, False]),
    ]
