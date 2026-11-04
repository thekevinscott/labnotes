import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        yield Path(folder)


def test_installed_daemon_reuses_socket_and_stop_cli(
    tmp_path: Path, uvx: dict[str, str], runtime: Path
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = \"{sys.executable} -c 'import time; time.sleep(600)'\"\n"
    )
    env = {**os.environ, **uvx, "XDG_RUNTIME_DIR": str(runtime)}
    base = ["uvx", "labnotes", "-c", str(root / ".labnotes.toml")]
    daemon = subprocess.Popen(
        [*base, "daemon", "exp"],
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    attached = socket.socket(socket.AF_UNIX)
    try:
        path = None
        for _ in range(200):
            sockets = list(runtime.glob("labnotes/*.sock"))
            if sockets:
                path = sockets[0]
                break
            time.sleep(0.05)
        assert path is not None, "installed daemon socket did not appear"
        attached.settimeout(5)
        attached.connect(str(path))
        attached.sendall(b'{"command":"attach"}\n')
        with attached.makefile("r") as reply:
            assert json.loads(reply.readline()) == {"ok": True}
        second = subprocess.Popen(
            [*base, "daemon", "exp"], cwd=root, env=env, stdout=subprocess.DEVNULL
        )
        assert second.wait(timeout=10) == 0
        assert list(runtime.glob("labnotes/*.sock")) == [path]
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(5)
            client.connect(str(path))
            client.sendall(b'{"command":"start","options":{}}\n')
            with client.makefile("r") as reply:
                assert json.loads(reply.readline())["ok"] is True
        for _ in range(100):
            records = list(root.glob("exp/runs/*/run.json"))
            if records and json.loads(records[0].read_text()).get("pid"):
                break
            time.sleep(0.05)
        assert records, "installed daemon did not start a cell"
        listed = subprocess.run(
            [*base, "experiments", "--format", "json"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        [row] = json.loads(listed.stdout)
        assert row["daemon"] is True
        assert row["running_cells"] == 1
        stopped = subprocess.run(
            [*base, "experiments", "exp", "stop"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
        )
        assert stopped.returncode == 0, stopped.stderr
        for _ in range(100):
            record = json.loads(records[0].read_text())
            if record.get("ended") is not None:
                break
            time.sleep(0.05)
        assert record["ended_by"] == "stop"
    finally:
        attached.close()
        if daemon.poll() is None:
            daemon.terminate()
        daemon.communicate(timeout=15)
