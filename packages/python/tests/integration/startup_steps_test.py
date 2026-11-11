import asyncio
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import psutil
import pytest

from labnotes.daemon.ensure import ensure_daemon
from labnotes.daemon.request_start import request_start
from labnotes.read_config import read_config

STEPS = ["Starting up", "Preparing experiment", "Preparing codebase", "Starting run"]


@pytest.fixture(autouse=True)
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": folder}):
            yield Path(folder)


@pytest.fixture
def root(tmp_path: Path) -> Iterator[Path]:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text("continues = false\ncommand = 'true'\n")
    for args in (
        ["init", "-q"],
        ["add", "."],
        ["-c", "user.name=T", "-c", "user.email=t@e.x", "commit", "-qm", "init"],
    ):
        subprocess.run(["git", *args], cwd=root, check=True)
    yield root
    config = str(root / ".labnotes.toml")
    owners = [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (process.info["cmdline"] or [])
        and "daemon" in (process.info["cmdline"] or [])
    ]
    for process in owners:
        process.terminate()
    psutil.wait_procs(owners, timeout=15)


@pytest.mark.parametrize("running", [False, True])
def test_start_reports_each_merged_step_once(root: Path, running: bool) -> None:
    config = read_config(root / ".labnotes.toml")
    steps: list[str] = []

    async def start() -> None:
        if running:
            await ensure_daemon(config, "exp")
        await request_start(
            config, "exp", {"command": "start", "options": {}}, steps.append
        )

    asyncio.run(start())
    assert steps == STEPS
