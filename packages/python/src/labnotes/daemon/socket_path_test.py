import hashlib
import os
import tempfile
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
from labnotes.runner.run_state import journal_folder


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


def test_discovery_records_live_with_journals(tmp_path: Path) -> None:
    project = config(tmp_path)
    folder = journal_folder(tmp_path / "experiments/exp/runs")
    assert discovery_folder(project, "exp") == folder
    assert socket_record(project, "exp").parent == folder
    assert lock_path(project, "exp").parent == folder
    assert socket_record(project, "exp").stem == daemon_key(project, "exp")
