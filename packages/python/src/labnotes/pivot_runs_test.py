from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.pivot_runs import pivot_runs


@pytest.fixture(autouse=True)
def grid_cell() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.pivot_runs.grid_cell",
        side_effect=lambda values, counts: {"values": values, "counts": counts},
    ) as grid_cell:
        yield grid_cell


def test_puts_the_last_axis_across_and_the_rest_down() -> None:
    axes: dict[str, list[object]] = {"model": ["a", "b"], "lang": ["en", "fr"]}
    found = {"model": "a", "lang": "fr", "runs": 3, "completed": 2}

    grid = pivot_runs(axes, [found])

    assert grid["row_keys"] == ["model"]
    assert grid["column_key"] == "lang"
    assert grid["columns"] == ["en", "fr"]
    assert grid["rows"] == [
        {
            "labels": ["a"],
            "cells": [
                {"values": {"model": "a", "lang": "en"}, "counts": {}},
                {"values": {"model": "a", "lang": "fr"}, "counts": found},
            ],
        },
        {
            "labels": ["b"],
            "cells": [
                {"values": {"model": "b", "lang": "en"}, "counts": {}},
                {"values": {"model": "b", "lang": "fr"}, "counts": {}},
            ],
        },
    ]


def test_crosses_every_leading_axis_into_rows() -> None:
    axes: dict[str, list[object]] = {"a": [1, 2], "b": ["x", "y"], "c": [True, False]}

    grid = pivot_runs(axes, [])

    assert grid["row_keys"] == ["a", "b"]
    assert [row["labels"] for row in grid["rows"]] == [
        [1, "x"],
        [1, "y"],
        [2, "x"],
        [2, "y"],
    ]


def test_matches_booleans_to_the_integers_sql_returns() -> None:
    axes: dict[str, list[object]] = {"flag": [True, False]}
    found: dict[str, object] = {"flag": 1, "runs": 1, "completed": 1}

    [row] = pivot_runs(axes, [found])["rows"]

    assert row["labels"] == []
    assert row["cells"] == [
        {"values": {"flag": True}, "counts": found},
        {"values": {"flag": False}, "counts": {}},
    ]


def test_one_cell_when_nothing_varies() -> None:
    found: dict[str, object] = {"runs": 4, "completed": 3}

    grid = pivot_runs({}, [found])

    assert grid["row_keys"] == []
    assert grid["column_key"] is None
    assert grid["rows"] == [{"labels": [], "cells": [{"values": {}, "counts": found}]}]
