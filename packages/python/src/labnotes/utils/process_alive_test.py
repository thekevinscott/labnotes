from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.utils.process_alive import process_alive


class Gone(Exception):
    pass


class Denied(Exception):
    pass


@pytest.fixture
def psutil() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.utils.process_alive.psutil") as psutil:
        psutil.NoSuchProcess = Gone
        psutil.AccessDenied = Denied
        yield psutil


def started(psutil: mock.MagicMock, created: float) -> None:
    psutil.Process.return_value.create_time.return_value = created


def test_is_alive_while_the_same_process_runs(psutil: mock.MagicMock) -> None:
    started(psutil, 50.0)

    assert process_alive(7, 50.0) is True
    psutil.Process.assert_called_once_with(7)


def test_is_dead_once_the_process_is_gone(psutil: mock.MagicMock) -> None:
    psutil.Process.side_effect = Gone()

    assert process_alive(7, 50.0) is False


@pytest.mark.parametrize("created", [51.0, 49.0])
def test_is_dead_when_another_process_reused_the_pid(
    psutil: mock.MagicMock, created: float
) -> None:
    started(psutil, created)

    assert process_alive(7, 50.0) is False


@pytest.mark.parametrize("created", [0.004, 0.01])
def test_allows_for_rounding_in_the_recorded_start(
    psutil: mock.MagicMock, created: float
) -> None:
    started(psutil, created)

    assert process_alive(7, 0.0) is True


def test_trusts_a_live_pid_without_a_recorded_start(psutil: mock.MagicMock) -> None:
    started(psutil, 50.0)

    assert process_alive(7, None) is True


def test_counts_a_process_it_cannot_inspect_as_alive(psutil: mock.MagicMock) -> None:
    psutil.Process.side_effect = Denied()

    assert process_alive(7, 50.0) is True
