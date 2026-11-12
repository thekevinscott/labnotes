from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.daemon.listening import listening


@pytest.fixture
def probe() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.daemon.listening.socket") as module:
        module.AF_UNIX = 1
        client = module.socket.return_value.__enter__.return_value
        yield client
        module.socket.assert_called_once_with(1)


def test_a_server_that_accepts_is_listening(probe: mock.MagicMock) -> None:
    assert listening(Path("/run/live.sock")) is True
    probe.settimeout.assert_called_once_with(1)
    probe.connect.assert_called_once_with("/run/live.sock")


def test_a_full_backlog_still_counts_as_listening(probe: mock.MagicMock) -> None:
    probe.connect.side_effect = TimeoutError
    assert listening(Path("/run/busy.sock")) is True


@pytest.mark.parametrize(
    "error", [ConnectionRefusedError, FileNotFoundError, PermissionError]
)
def test_a_refused_or_missing_socket_is_not_listening(
    probe: mock.MagicMock, error: type[OSError]
) -> None:
    probe.connect.side_effect = error
    assert listening(Path("/run/gone.sock")) is False
