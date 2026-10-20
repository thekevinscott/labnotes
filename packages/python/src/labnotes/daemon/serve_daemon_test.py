from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.daemon.serve_daemon import serve_daemon


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.daemon.serve_daemon.hold_folder") as hold_folder,
        mock.patch(
            "labnotes.daemon.serve_daemon.run_daemon", new=mock.AsyncMock()
        ) as run_daemon,
    ):
        yield {"hold_folder": hold_folder, "run_daemon": run_daemon}


def test_serves_while_holding_the_project(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    config = mock.Mock(root=Path("/p"))
    lock = collaborators["hold_folder"].return_value

    def held(_: object) -> None:
        lock.__enter__.assert_called_once()
        lock.__exit__.assert_not_called()

    collaborators["run_daemon"].side_effect = held

    serve_daemon(config)

    collaborators["hold_folder"].assert_called_once_with(Path("/p"))
    collaborators["run_daemon"].assert_awaited_once_with(config)
    lock.__exit__.assert_called_once()


def test_leaves_a_held_project_to_its_daemon(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    lock = collaborators["hold_folder"].return_value
    lock.__enter__.side_effect = BlockingIOError()

    serve_daemon(mock.Mock(root=Path("/p")))

    collaborators["run_daemon"].assert_not_awaited()
