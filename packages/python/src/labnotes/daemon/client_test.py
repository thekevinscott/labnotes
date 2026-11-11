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
        mock.patch(
            "labnotes.daemon.client.socket_path",
            return_value=tmp_path / "none.sock",
        ),
        mock.patch("labnotes.daemon.client.listening", return_value=False),
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


def test_a_live_daemon_is_found_after_its_record_and_lock_are_deleted(
    paths: tuple[Path, Path], tmp_path: Path
) -> None:
    live = tmp_path / "live.sock"
    with (
        mock.patch("labnotes.daemon.client.socket_path", return_value=live),
        mock.patch("labnotes.daemon.client.listening", return_value=True) as probe,
    ):
        assert daemon_socket(mock.Mock(), "exp") == live
    probe.assert_called_once_with(live)


def test_a_live_socket_is_kept_when_its_lock_file_was_replaced(
    paths: tuple[Path, Path], tmp_path: Path
) -> None:
    record, lock = paths
    live = tmp_path / "live.sock"
    live.touch()
    record.write_text(str(live))
    lock.touch()
    with mock.patch("labnotes.daemon.client.listening", return_value=True) as probe:
        assert daemon_socket(mock.Mock(), "exp") == live
    probe.assert_called_once_with(live)
    assert live.exists()
    assert record.exists()


def test_a_live_socket_is_kept_when_its_lock_file_is_gone(
    paths: tuple[Path, Path], tmp_path: Path
) -> None:
    record, _ = paths
    live = tmp_path / "live.sock"
    live.touch()
    record.write_text(str(live))
    with mock.patch("labnotes.daemon.client.listening", return_value=True):
        assert daemon_socket(mock.Mock(), "exp") == live
    assert live.exists()
    assert record.exists()
