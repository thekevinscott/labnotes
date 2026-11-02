from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.run_locked import run_locked


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.runner.run_locked.os") as os,
        mock.patch("labnotes.runner.run_locked.claim_run") as claim_run,
    ):
        yield {"os": os, "claim_run": claim_run}


def test_is_locked_while_someone_holds_the_lock(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["claim_run"].return_value = None

    assert run_locked(Path("/runs/r1"))

    collaborators["claim_run"].assert_called_once_with(Path("/runs/r1"))
    collaborators["os"].close.assert_not_called()


def test_lets_go_of_a_lock_nobody_held(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["claim_run"].return_value = 9

    assert not run_locked(Path("/runs/r1"))

    collaborators["os"].close.assert_called_once_with(9)
