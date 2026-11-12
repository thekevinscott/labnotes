import hashlib
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.daemon.socket_path import (
    daemon_key,
    discovery_folder,
    lock_path,
    runtime_folder,
    socket_path,
    socket_record,
)


def config(root: Path) -> mock.Mock:
    return mock.Mock(
        root=root,
        experiments="experiments/{experiment}",
        runs="experiments/{experiment}/runs/{run}",
    )


def test_deep_experiment_gets_short_versioned_socket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = Path(tempfile.mkdtemp(prefix="ln-socket-"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    project = config(tmp_path / ("deep/" * 30))
    with mock.patch("labnotes.daemon.socket_path.version", return_value="2.3.4"):
        path = socket_path(project, "exp")
        identity = f"{(project.root / 'experiments/exp').resolve()}\0" "2.3.4"
        assert (
            daemon_key(project, "exp")
            == hashlib.sha256(identity.encode()).hexdigest()[:16]
        )
        assert len(os.fsencode(path)) < 104
        assert path.parent == runtime / "labnotes"
        assert path.parent.stat().st_mode & 0o777 == 0o700
        assert socket_path(project, "other") != path
    with mock.patch("labnotes.daemon.socket_path.version", return_value="2.3.5"):
        assert socket_path(project, "exp") != path


def test_missing_runtime_dir_uses_owner_only_temp_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    folder = runtime_folder()
    assert folder == tmp_path / f"labnotes-{os.getuid()}"
    assert folder.stat().st_mode & 0o777 == 0o700
    assert socket_path(config(tmp_path), "exp").parent == folder


def test_discovery_folder_is_stable_per_runs_folder(tmp_path: Path) -> None:
    moved = mock.Mock(
        root=tmp_path,
        experiments="experiments/{experiment}",
        runs="experiments/../experiments/{experiment}/runs/{run}",
    )
    assert discovery_folder(moved, "exp") == discovery_folder(config(tmp_path), "exp")
    assert discovery_folder(config(tmp_path), "other") != discovery_folder(
        config(tmp_path), "exp"
    )


@pytest.mark.parametrize("state_home", [None, ""])
def test_discovery_folder_defaults_to_local_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state_home: str | None
) -> None:
    if state_home is None:
        monkeypatch.delenv("XDG_STATE_HOME")
    else:
        monkeypatch.setenv("XDG_STATE_HOME", state_home)
    monkeypatch.setenv("HOME", str(tmp_path))
    folder = discovery_folder(config(tmp_path), "exp")
    assert folder.parent == tmp_path / ".local/state/labnotes/run-state"


def test_discovery_records_live_in_run_state(tmp_path: Path) -> None:
    project = config(tmp_path)
    runs = tmp_path / "experiments/exp/runs"
    key = hashlib.sha256(str(runs.resolve()).encode()).hexdigest()[:16]
    folder = Path(os.environ["XDG_STATE_HOME"]) / "labnotes/run-state" / key
    assert discovery_folder(project, "exp") == folder
    assert socket_record(project, "exp").parent == folder
    assert lock_path(project, "exp").parent == folder
    assert socket_record(project, "exp").stem == daemon_key(project, "exp")


@pytest.fixture
def nested_runtime(tmp_path: Path) -> Iterator[Path]:
    runtime = tmp_path / "missing" / "run"
    with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(runtime)}):
        yield runtime


def test_runtime_folder_is_created_under_a_missing_parent(
    nested_runtime: Path,
) -> None:
    assert runtime_folder() == nested_runtime / "labnotes"


def test_runtime_folder_is_private_from_creation(nested_runtime: Path) -> None:
    umask = os.umask(0o022)
    try:
        with mock.patch.object(Path, "chmod"):
            folder = runtime_folder()
    finally:
        os.umask(umask)
    assert folder.stat().st_mode & 0o777 == 0o700
