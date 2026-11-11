import socket
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
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
        mock.patch(
            "labnotes.daemon.client.socket_path",
            return_value=tmp_path / "none.sock",
            create=True,
        ),
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


@pytest.fixture
def flock() -> Iterator[mock.Mock]:
    with mock.patch("labnotes.daemon.client.fcntl") as fcntl:
        fcntl.LOCK_EX, fcntl.LOCK_NB, fcntl.LOCK_UN = 2, 4, 8
        yield fcntl.flock


def test_checking_the_lock_never_waits_for_its_holder(
    paths: tuple[Path, Path], flock: mock.Mock
) -> None:
    record, lock = paths
    record.write_text("/tmp/held.sock")
    lock.touch()
    flock.side_effect = BlockingIOError
    assert daemon_socket(mock.Mock(), "exp") == Path("/tmp/held.sock")
    assert flock.call_args.args[1] == 2 | 4


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
    paths: tuple[Path, Path], tmp_path: Path, flock: mock.Mock
) -> None:
    record, lock = paths
    record.write_text(str(tmp_path / "gone.sock"))
    lock.touch()

    def unlock(descriptor: int, operation: int) -> None:
        if operation == 8:
            record.unlink()

    flock.side_effect = unlock
    assert daemon_socket(mock.Mock(), "exp") is None


@pytest.fixture
def live_socket() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-") as folder:
        path = Path(folder) / "live.sock"
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(path))
            server.listen()
            yield path


def test_a_live_daemon_is_found_after_its_record_and_lock_are_deleted(
    paths: tuple[Path, Path], live_socket: Path
) -> None:
    with mock.patch(
        "labnotes.daemon.client.socket_path", return_value=live_socket, create=True
    ):
        assert daemon_socket(mock.Mock(), "exp") == live_socket
    assert live_socket.exists()


def test_a_live_socket_is_kept_when_its_lock_file_was_replaced(
    paths: tuple[Path, Path], live_socket: Path
) -> None:
    record, lock = paths
    record.write_text(str(live_socket))
    lock.touch()
    assert daemon_socket(mock.Mock(), "exp") == live_socket
    assert live_socket.exists()
    assert record.exists()
