import asyncio
import os
import shutil
import socket
import sys
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import psutil
import pytest

from labnotes.daemon.client import daemon_socket
from labnotes.daemon.command import command
from labnotes.daemon.ensure import ensure_daemon
from labnotes.models import LabnotesConfig
from labnotes.read_config import read_config


@pytest.fixture
def runtime_env() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as runtime:
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": runtime}):
            yield Path(runtime)


def daemons(root: Path) -> list[psutil.Process]:
    config = str(root / ".labnotes.toml")
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (process.info["cmdline"] or [])
        and "daemon" in (process.info["cmdline"] or [])
    ]


@pytest.fixture
def project(tmp_path: Path, runtime_env: Path) -> Iterator[LabnotesConfig]:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(f'command = "{sys.executable} -V"\n')
    yield read_config(root / ".labnotes.toml")
    owners = daemons(root)
    for process in owners:
        process.terminate()
    psutil.wait_procs(owners, timeout=15)


def run_state() -> Path:
    return Path(os.environ["XDG_STATE_HOME"]) / "labnotes" / "run-state"


def attach(path: Path) -> socket.socket:
    client = socket.socket(socket.AF_UNIX)
    client.connect(str(path))
    client.sendall(b'{"command":"attach"}\n')
    client.recv(4096)
    return client


def test_deleting_run_state_keeps_a_live_daemon_reachable(
    project: LabnotesConfig,
) -> None:
    asyncio.run(ensure_daemon(project, "exp"))
    path = daemon_socket(project, "exp")
    assert path is not None
    with attach(path):
        shutil.rmtree(run_state())
        assert daemon_socket(project, "exp") == path
        assert command(project, "exp", {"command": "ping"}) == {"ok": True}
        asyncio.run(ensure_daemon(project, "exp"))
        assert len(daemons(project.root)) == 1
        assert path.exists()
        assert command(project, "exp", {"command": "ping"}) == {"ok": True}


def test_a_daemon_marks_run_state_as_live(project: LabnotesConfig) -> None:
    asyncio.run(ensure_daemon(project, "exp"))
    marker = run_state() / "README"
    assert "Do not delete" in marker.read_text()
