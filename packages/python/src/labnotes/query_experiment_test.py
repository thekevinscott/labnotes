import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.query_experiment import query_experiment

LISTED = [
    {"name": "a", "study": "s1", "runs": 3},
    {"name": "b", "study": None, "runs": 0},
]
ROWS = [{"n": 3}]


@pytest.fixture
def stores() -> Iterator[dict[str, mock.Mock]]:
    experiments = mock.Mock(ready=mock.AsyncMock())
    runs = mock.Mock(ready=mock.AsyncMock(), query=mock.AsyncMock(return_value=ROWS))
    with (
        mock.patch(
            "labnotes.query_experiment.open_experiments", return_value=experiments
        ) as open_experiments,
        mock.patch(
            "labnotes.query_experiment.open_runs", return_value=runs
        ) as open_runs,
        mock.patch(
            "labnotes.query_experiment.list_experiments",
            new_callable=mock.AsyncMock,
            return_value=LISTED,
        ) as list_experiments,
        mock.patch(
            "labnotes.query_experiment.scope_runs", return_value="SCOPED"
        ) as scope_runs,
    ):
        yield {
            "experiments": experiments,
            "runs": runs,
            "open_experiments": open_experiments,
            "open_runs": open_runs,
            "list_experiments": list_experiments,
            "scope_runs": scope_runs,
        }


def query(name: str, sql: str | None) -> object:
    return asyncio.run(query_experiment(Path("exp"), Path("data"), name, sql))


def test_returns_the_named_experiment_without_sql(
    stores: dict[str, mock.Mock],
) -> None:
    assert query("a", None) == LISTED[0]
    stores["open_experiments"].assert_called_once_with(Path("exp"))
    stores["open_runs"].assert_called_once_with(Path("data"))
    stores["experiments"].ready.assert_awaited_once()
    stores["runs"].ready.assert_awaited_once()
    stores["list_experiments"].assert_awaited_once_with(
        stores["experiments"], stores["runs"]
    )
    stores["runs"].query.assert_not_awaited()


def test_runs_the_sql_scoped_to_the_experiments_study(
    stores: dict[str, mock.Mock],
) -> None:
    assert query("a", "SELECT 1") == ROWS
    stores["scope_runs"].assert_called_once_with("SELECT 1", "s1")
    stores["runs"].query.assert_awaited_once_with("SCOPED")


def test_rejects_an_unknown_experiment(stores: dict[str, mock.Mock]) -> None:
    with pytest.raises(LookupError, match="no experiment named 'zzz'"):
        query("zzz", None)


def test_rejects_sql_for_an_experiment_without_a_study(
    stores: dict[str, mock.Mock],
) -> None:
    with pytest.raises(LookupError, match="'b' has no study"):
        query("b", "SELECT 1")
    stores["runs"].query.assert_not_awaited()


def test_summarizes_an_experiment_without_a_study(
    stores: dict[str, mock.Mock],
) -> None:
    assert query("b", None) == LISTED[1]
