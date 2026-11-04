from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.daemon.client import daemon_socket


@pytest.fixture
def paths(tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    record = tmp_path / "socket.record"
    lock = tmp_path / "daemon.lock"
    with (
        mock.patch("labnotes.daemon.client.socket_record", return_value=record),
        mock.patch("labnotes.daemon.client.lock_path", return_value=lock),
    ):
        yield record, lock


def test_missing_and_stale_socket_are_not_running(
    paths: tuple[Path, Path], tmp_path: Path
) -> None:
    record, lock = paths
    assert daemon_socket(mock.Mock(), "exp") is None
    stale = tmp_path / "stale.sock"
    stale.touch()
    record.write_text(str(stale))
    lock.touch()
    with mock.patch("labnotes.daemon.client.fcntl.flock"):
        assert daemon_socket(mock.Mock(), "exp") is None
    assert not stale.exists()
    assert not record.exists()


def test_record_without_lock_is_cleaned_as_stale(
    paths: tuple[Path, Path], tmp_path: Path
) -> None:
    record, _ = paths
    stale = tmp_path / "orphan.sock"
    stale.touch()
    record.write_text(str(stale))
    assert daemon_socket(mock.Mock(), "exp") is None
    assert not stale.exists()
    assert not record.exists()


def test_held_lock_exposes_recorded_socket(paths: tuple[Path, Path]) -> None:
    record, lock = paths
    record.write_text("/tmp/held.sock")
    lock.touch()
    with mock.patch("labnotes.daemon.client.fcntl.flock", side_effect=BlockingIOError):
        assert daemon_socket(mock.Mock(), "exp") == Path("/tmp/held.sock")
    assert record.exists()
