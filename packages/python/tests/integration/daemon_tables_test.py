import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from conftest import daemon_request, write

UNFINISHED = {
    "params": {},
    "created": "2026-10-17T00:00:00Z",
    "ended": None,
    "exit_code": None,
    "error": None,
}
COUNTING = """
import os, runpy, sys
import dirsql._async

log, *args = sys.argv[1:]
opened = dirsql._async.DirSQL.__init__

def counted(self, root=None, **options):
    with open(log, "a") as stream:
        stream.write(os.path.abspath(os.getcwd() if root is None else root) + "\\n")
    opened(self, root, **options)

dirsql._async.DirSQL.__init__ = counted
sys.argv = ["labnotes", *args]
runpy.run_module("labnotes", run_name="__main__", alter_sys=True)
"""


def read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    write(root / ".labnotes.toml", "")
    write(
        root / "exp/experiment.toml",
        f"continues = false\ncommand = '{sys.executable} -c pass'\n",
    )
    write(root / "other/experiment.toml", "continues = false\ncommand = 'true'\n")
    write(root / "exp/runs/lost/run.json", json.dumps(UNFINISHED))
    write(root / "other/runs/lost/run.json", json.dumps(UNFINISHED))
    return root


@pytest.fixture
def daemon(project: Path, tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    log = tmp_path / "dirsql.log"
    with TemporaryDirectory(prefix="ln-runtime-") as runtime:
        process = subprocess.Popen(
            [sys.executable, "-c", COUNTING, str(log)]
            + ["-c", str(project / ".labnotes.toml"), "daemon", "exp"],
            cwd=project,
            env={**os.environ, "XDG_RUNTIME_DIR": runtime},
        )
        try:
            for _ in range(300):
                sockets = list(Path(runtime).glob("labnotes/*.sock"))
                if sockets:
                    break
                time.sleep(0.1)
            [path] = sockets
            yield path, log
        finally:
            process.terminate()
            process.wait(timeout=30)


def finished(root: Path) -> bool:
    return any(
        read(path).get("exit_code") == 0 for path in root.glob("exp/runs/*/run.json")
    )


def test_a_start_reads_through_the_daemons_one_dirsql(
    project: Path, daemon: tuple[Path, Path]
) -> None:
    path, log = daemon

    assert daemon_request(path, "POST", "/start", {})["ok"] is True
    for _ in range(300):
        if finished(project):
            break
        time.sleep(0.1)
    assert finished(project)

    assert log.read_text().splitlines() == [str(project / "exp")]


def test_a_start_finalizes_only_its_own_experiments_lost_runs(
    project: Path, daemon: tuple[Path, Path]
) -> None:
    path, _ = daemon

    assert daemon_request(path, "POST", "/start", {})["ok"] is True

    assert read(project / "exp/runs/lost/run.json")["ended_by"] == "lost"
    assert read(project / "other/runs/lost/run.json") == UNFINISHED
