from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.claim_run import LOCK_FILE, claim_run


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.runner.claim_run.os") as os,
        mock.patch("labnotes.runner.claim_run.fcntl") as fcntl,
    ):
        os.open.return_value = 9
        yield {"os": os, "fcntl": fcntl}


def test_names_the_lock_file() -> None:
    assert LOCK_FILE == "run.lock"


def test_holds_the_lock_file_without_waiting(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    os, fcntl = collaborators["os"], collaborators["fcntl"]

    assert claim_run(Path("/runs/r1")) == 9

    os.open.assert_called_once_with(
        Path("/runs/r1/run.lock"), os.O_RDWR | os.O_CREAT, 0o644
    )
    fcntl.flock.assert_called_once_with(9, fcntl.LOCK_EX | fcntl.LOCK_NB)
    os.close.assert_not_called()


def test_gives_way_to_another_holder(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["fcntl"].flock.side_effect = BlockingIOError

    assert claim_run(Path("/runs/r1")) is None

    collaborators["os"].close.assert_called_once_with(9)
