import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tables.experiment_rows import experiment_rows

CONFIG = mock.Mock(mode="matrix", root=Path("/lab"))
RUN = {"id": "r", "folder": "a/runs/r", "ended": "t", "exit_code": 0, "error": None}


@pytest.fixture
def queries() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.tables.experiment_rows.open_tables") as open_tables,
        mock.patch(
            "labnotes.tables.experiment_rows.summarize_experiments",
            new=mock.AsyncMock(return_value=[{"name": "a"}]),
        ) as summarize,
        mock.patch(
            "labnotes.tables.experiment_rows.summarize_config",
            return_value={"completed_run": "c"},
        ) as summarize_config,
        mock.patch(
            "labnotes.tables.experiment_rows.list_experiment_runs",
            new=mock.AsyncMock(return_value=[RUN]),
        ) as list_runs,
        mock.patch(
            "labnotes.tables.experiment_rows.run_usage",
            new=mock.AsyncMock(return_value={"memory": None, "size": 7}),
        ) as run_usage,
    ):
        yield {
            "open_tables": open_tables,
            "summarize": summarize,
            "list_runs": list_runs,
            "summarize_config": summarize_config,
            "run_usage": run_usage,
        }


def test_summarizes_every_experiment(queries: dict[str, mock.MagicMock]) -> None:
    assert asyncio.run(experiment_rows(CONFIG, None, None)) == [{"name": "a"}]

    queries["open_tables"].assert_called_once_with(CONFIG)
    queries["summarize"].assert_awaited_once_with(
        queries["open_tables"].return_value, None
    )


def test_summarizes_one_experiment(queries: dict[str, mock.MagicMock]) -> None:
    assert asyncio.run(experiment_rows(CONFIG, "a", None)) == [{"name": "a"}]
    queries["list_runs"].assert_not_awaited()


def test_lists_one_experiments_runs(queries: dict[str, mock.MagicMock]) -> None:
    queries["summarize"].return_value = [{"name": "a", "config": '{"counts": "x"}'}]

    assert asyncio.run(experiment_rows(CONFIG, "a", "runs")) == [
        {**RUN, "memory": None, "size": 7}
    ]
    queries["run_usage"].assert_awaited_once_with(Path("/lab/a/runs/r"), False)

    queries["summarize_config"].assert_called_once_with({"counts": "x"}, "matrix")
    queries["list_runs"].assert_awaited_once_with(
        queries["open_tables"].return_value, "a", "c"
    )


def test_summarizes_a_missing_config_as_none(
    queries: dict[str, mock.MagicMock],
) -> None:
    queries["summarize"].return_value = [{"name": "a", "config": None}]

    asyncio.run(experiment_rows(CONFIG, "a", "runs"))

    queries["summarize_config"].assert_called_once_with(None, "matrix")


def test_returns_none_for_an_unknown_experiment(
    queries: dict[str, mock.MagicMock],
) -> None:
    queries["summarize"].return_value = []

    assert asyncio.run(experiment_rows(CONFIG, "zz", "runs")) is None
    queries["list_runs"].assert_not_awaited()


@pytest.mark.parametrize(
    ("ended", "exit_code", "error", "running"),
    [
        (None, None, None, True),
        ("t", None, None, False),
        (None, 1, None, False),
        (None, None, "boom", False),
    ],
)
def test_samples_memory_only_for_a_run_still_going(
    queries: dict[str, mock.MagicMock],
    ended: str | None,
    exit_code: int | None,
    error: str | None,
    running: bool,
) -> None:
    queries["summarize"].return_value = [{"name": "a", "config": None}]
    queries["list_runs"].return_value = [
        {**RUN, "ended": ended, "exit_code": exit_code, "error": error}
    ]

    asyncio.run(experiment_rows(CONFIG, "a", "runs"))

    queries["run_usage"].assert_awaited_once_with(Path("/lab/a/runs/r"), running)
