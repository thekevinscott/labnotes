import hashlib
import os
from importlib.metadata import version
from pathlib import Path
from unittest import mock

import pytest

from labnotes.daemon.socket_path import socket_path


def digest(root: Path) -> str:
    return hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:16]


def test_sits_in_a_fixed_folder_per_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("TMPDIR", str(tmp_path))

    path = socket_path(Path("/p"))

    folder = Path("/tmp") / f"labnotes-{os.getuid()}"
    assert path == folder / f"{digest(Path('/p'))}-{version('labnotes')}.sock"
    assert folder.stat().st_mode & 0o777 == 0o700


def test_reuses_an_existing_folder() -> None:
    assert socket_path(Path("/p")) == socket_path(Path("/p"))


def test_names_each_project_apart_and_stays_short() -> None:
    deep = Path("/p") / ("long-folder-name-" * 20)

    assert socket_path(Path("/p")) != socket_path(Path("/q"))
    assert len(str(socket_path(deep))) < 60


def test_names_a_project_the_same_through_a_symlink(tmp_path: Path) -> None:
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")

    assert socket_path(tmp_path / "link") == socket_path(tmp_path / "real")


def test_names_each_labnotes_version_apart() -> None:
    with mock.patch("labnotes.daemon.socket_path.version", return_value="1.2.3"):
        older = socket_path(Path("/p"))

    assert older.name.endswith("-1.2.3.sock")
    assert socket_path(Path("/p")) != older
