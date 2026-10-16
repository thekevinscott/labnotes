import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.dump_experiments import dump_experiments


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.dump_experiments.open_experiments") as open_experiments,
        mock.patch("labnotes.dump_experiments.open_runs") as open_runs,
        mock.patch(
            "labnotes.dump_experiments.list_experiments",
            new_callable=mock.AsyncMock,
            return_value=[{"name": "a"}],
        ) as list_experiments,
    ):
        for opener in (open_experiments, open_runs):
            opener.return_value.ready = mock.AsyncMock()
        yield {
            "open_experiments": open_experiments,
            "open_runs": open_runs,
            "list_experiments": list_experiments,
        }


def test_opens_both_folders_and_lists_once_ready(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    listed = asyncio.run(dump_experiments(Path("exp"), Path("data")))

    assert listed == [{"name": "a"}]
    collaborators["open_experiments"].assert_called_once_with(Path("exp"))
    collaborators["open_runs"].assert_called_once_with(Path("data"))
    experiments = collaborators["open_experiments"].return_value
    runs = collaborators["open_runs"].return_value
    experiments.ready.assert_awaited_once()
    runs.ready.assert_awaited_once()
    collaborators["list_experiments"].assert_awaited_once_with(experiments, runs)
