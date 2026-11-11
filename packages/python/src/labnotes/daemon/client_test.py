import fcntl
import os
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


def test_stale_record_for_a_vanished_socket_is_cleaned(
    paths: tuple[Path, Path], tmp_path: Path
) -> None:
    record, lock = paths
    record.write_text(str(tmp_path / "gone.sock"))
    assert daemon_socket(mock.Mock(), "exp") is None
    assert not record.exists()
    record.write_text(str(tmp_path / "gone.sock"))
    lock.touch()
    assert daemon_socket(mock.Mock(), "exp") is None
    assert not record.exists()


def test_a_lock_held_elsewhere_exposes_the_socket(paths: tuple[Path, Path]) -> None:
    record, lock = paths
    record.write_text("/tmp/held.sock")
    lock.touch()
    holder = os.open(lock, os.O_RDONLY)
    try:
        fcntl.flock(holder, fcntl.LOCK_EX)
        assert daemon_socket(mock.Mock(), "exp") == Path("/tmp/held.sock")
    finally:
        os.close(holder)


def test_a_record_another_client_cleaned_first_is_not_an_error(
    paths: tuple[Path, Path], tmp_path: Path
) -> None:
    record, lock = paths
    record.write_text(str(tmp_path / "gone.sock"))

    def cleaned_elsewhere(*_: object) -> Path:
        record.unlink()
        return lock

    with mock.patch("labnotes.daemon.client.lock_path", side_effect=cleaned_elsewhere):
        assert daemon_socket(mock.Mock(), "exp") is None


def test_a_record_cleaned_while_checking_the_lock_is_not_an_error(
    paths: tuple[Path, Path], tmp_path: Path
) -> None:
    record, lock = paths
    record.write_text(str(tmp_path / "gone.sock"))
    lock.touch()

    def unlock(descriptor: int, operation: int) -> None:
        if operation == fcntl.LOCK_UN:
            record.unlink()

    with mock.patch("labnotes.daemon.client.fcntl.flock", side_effect=unlock):
        assert daemon_socket(mock.Mock(), "exp") is None
