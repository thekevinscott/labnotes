import hashlib
import os
from pathlib import Path

import pytest

from labnotes.daemon.socket_path import socket_path


def digest(root: Path) -> str:
    return hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:16]


def test_sits_in_the_runtime_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))

    path = socket_path(tmp_path / "project")

    assert (
        path == tmp_path / "run" / "labnotes" / f"{digest(tmp_path / 'project')}.sock"
    )
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_falls_back_to_a_temp_folder_per_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))

    path = socket_path(Path("/p"))

    assert path == tmp_path / f"labnotes-{os.getuid()}" / f"{digest(Path('/p'))}.sock"
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_ignores_an_empty_runtime_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", "")
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))

    assert socket_path(Path("/p")).parent == tmp_path / f"labnotes-{os.getuid()}"


def test_reuses_an_existing_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

    assert socket_path(Path("/p")) == socket_path(Path("/p"))


def test_names_each_project_apart_and_stays_short(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    deep = Path("/p") / ("long-folder-name-" * 20)

    assert socket_path(Path("/p")) != socket_path(Path("/q"))
    assert len(str(socket_path(deep))) < len(str(tmp_path)) + 40


def test_names_a_project_the_same_through_a_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")

    assert socket_path(tmp_path / "link") == socket_path(tmp_path / "real")
