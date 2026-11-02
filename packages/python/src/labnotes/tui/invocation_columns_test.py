from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.invocation_columns import Experiment, invocation_columns

CONFIG = {"params": {"m": [1, 2]}}


@pytest.fixture(autouse=True)
def run_columns() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.tui.invocation_columns.run_columns",
        side_effect=lambda config: ["id", "m", "started"],
    ) as found:
        yield found


def test_lists_a_status_column_then_the_run_columns(
    run_columns: mock.MagicMock,
) -> None:
    experiment = Experiment(Path("/p"), "alpha", {}, CONFIG)

    assert invocation_columns(experiment) == [
        {"key": "status", "label": ""},
        {"key": "id", "label": "id"},
        {"key": "m", "label": "m"},
        {"key": "started", "label": "started"},
    ]
    run_columns.assert_called_once_with(CONFIG)


def test_counts_runs_after_the_id_when_runs_are_grouped() -> None:
    experiment = Experiment(Path("/p"), "alpha", {}, CONFIG, groups=())

    assert [column["key"] for column in invocation_columns(experiment)] == [
        "status",
        "id",
        "runs",
        "m",
        "started",
    ]
    assert invocation_columns(experiment)[2] == {"key": "runs", "label": "runs"}
