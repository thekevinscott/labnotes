import json
import os
import subprocess
import sys
from pathlib import Path

import psutil

from conftest import write


UNFINISHED = {
    "params": {},
    "created": "2026-10-17T00:00:00Z",
    "ended": None,
    "exit_code": None,
    "error": None,
}


def add_run(root: Path, name: str, **fields: object) -> Path:
    path = root / f"exp/runs/{name}/run.json"
    write(path, json.dumps({**UNFINISHED, **fields}))
    return path


def read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_run_start_ends_runs_whose_process_died(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "exp/experiment.toml", f"command = '{sys.executable} -c pass'\n")
    exited = subprocess.Popen([sys.executable, "-c", ""])
    created = psutil.Process(exited.pid).create_time()
    exited.wait()
    me = psutil.Process(os.getpid())
    never_launched = add_run(tmp_path, "never")
    died = add_run(tmp_path, "died", pid=exited.pid, pid_created=created)
    reused = add_run(tmp_path, "reused", pid=me.pid, pid_created=me.create_time() - 60)
    alive = add_run(tmp_path, "alive", pid=me.pid, pid_created=me.create_time())
    done = add_run(tmp_path, "done", exit_code=0, ended="2026-10-17T00:01:00Z")

    labnotes = Path(sys.executable).parent / "labnotes"
    subprocess.run(
        [labnotes, "-c", str(tmp_path / ".labnotes.toml"), "experiments", "exp", "run"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    for path in (never_launched, died, reused):
        run = read(path)
        assert run["ended_by"] == "lost"
        assert run["ended"] is not None
        assert run["exit_code"] is None
    assert read(died)["pid"] == exited.pid
    assert read(alive) == {**UNFINISHED, "pid": me.pid, "pid_created": me.create_time()}
    assert "ended_by" not in read(done)
