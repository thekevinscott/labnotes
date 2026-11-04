import asyncio
import fcntl
import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import psutil

from labnotes.daemon.client import daemon_socket
from labnotes.daemon.ensure import ensure_daemon
from labnotes.daemon.socket_path import lock_path
from labnotes.read_config import read_config


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        yield Path(folder)


def command(root: Path, *args: str) -> list[str]:
    return [
        str(Path(sys.executable).parent / "labnotes"),
        "-c",
        str(root / ".labnotes.toml"),
        *args,
    ]


def wait_for_socket(runtime: Path) -> Path:
    for _ in range(100):
        sockets = list(runtime.glob("labnotes/*.sock"))
        if sockets:
            return sockets[0]
        time.sleep(0.05)
    raise AssertionError("daemon socket did not appear")


def request(path: Path, message: dict[str, object]) -> dict[str, object]:
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(5)
        client.connect(str(path))
        client.sendall((json.dumps(message) + "\n").encode())
        with client.makefile("r") as reply:
            return json.loads(reply.readline())


def test_concurrent_starters_reuse_one_daemon(
    tmp_path: Path, runtime: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    config_path = root / ".labnotes.toml"
    config_path.write_text("")
    (root / "exp/experiment.toml").write_text("command = 'true'\n")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    config = read_config(config_path)

    async def start_both() -> None:
        lock = lock_path(config, "exp")
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open("a+b") as held:
            fcntl.flock(held, fcntl.LOCK_EX)

            async def release_probe() -> None:
                await asyncio.sleep(0.5)
                fcntl.flock(held, fcntl.LOCK_UN)

            await asyncio.gather(
                ensure_daemon(config, "exp"),
                ensure_daemon(config, "exp"),
                release_probe(),
            )

    try:
        asyncio.run(start_both())
        path = daemon_socket(config, "exp")
        assert path is not None
        assert path == wait_for_socket(runtime)
        for _ in range(30):
            owners = [
                process
                for process in psutil.process_iter(["cmdline"])
                if str(config_path) in (process.info["cmdline"] or [])
                and "daemon" in (process.info["cmdline"] or [])
            ]
            if len(owners) == 1:
                break
            time.sleep(0.1)
        assert len(owners) == 1
    finally:
        for process in psutil.process_iter(["cmdline"]):
            if str(config_path) in (process.info["cmdline"] or []) and "daemon" in (
                process.info["cmdline"] or []
            ):
                process.terminate()
                process.wait(timeout=15)


def test_daemon_lists_running_cell_and_stop_command_stops_it(
    tmp_path: Path, runtime: Path
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = \"{sys.executable} -c 'import time; time.sleep(600)'\"\n"
    )
    env = {**os.environ, "XDG_RUNTIME_DIR": str(runtime)}
    daemon = subprocess.Popen(
        command(root, "daemon", "exp"),
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        path = wait_for_socket(runtime)
        answer = request(path, {"command": "start", "options": {}})
        assert answer["ok"] is True, answer
        assert Path(str(answer["journal"])).exists() or answer["journal"]
        for _ in range(100):
            records = list(root.glob("exp/runs/*/run.json"))
            if records and json.loads(records[0].read_text()).get("pid"):
                break
            time.sleep(0.05)
        assert records, "cell did not start"
        stray = root / "exp/runs/stale/run.json"
        stray.parent.mkdir()
        stray.write_text(json.dumps({"created": "2026-01-01T00:00:00Z", "ended": None}))
        listed = subprocess.run(
            command(root, "experiments", "--format", "json"),
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
            command(root, "experiments", "exp", "stop"),
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
        )
        assert stopped.returncode == 0, stopped.stderr
        assert "stop" in stopped.stdout.lower()
        for _ in range(100):
            record = json.loads(records[0].read_text())
            if record.get("ended") is not None:
                break
            time.sleep(0.05)
        assert record["ended_by"] == "stop"
    finally:
        if daemon.poll() is None:
            daemon.terminate()
        daemon.communicate(timeout=15)


def test_stop_without_daemon_reports_error(tmp_path: Path) -> None:
    (tmp_path / "exp").mkdir()
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp/experiment.toml").write_text("command = 'true'\n")
    result = subprocess.run(
        command(tmp_path, "experiments", "exp", "stop"),
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "no daemon" in result.stderr.lower()


def test_two_starts_share_one_daemon_and_keep_journals_separate(
    tmp_path: Path, runtime: Path
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        "continues = false\n"
        f"command = \"{sys.executable} -c 'import time; time.sleep(600)'\"\n"
        "[params]\nm = ['a', 'b']\n"
    )
    env = {**os.environ, "XDG_RUNTIME_DIR": str(runtime)}
    daemon = subprocess.Popen(
        command(root, "daemon", "exp"), cwd=root, env=env, stdout=subprocess.PIPE
    )
    try:
        path = wait_for_socket(runtime)
        first = request(path, {"command": "start", "options": {"only": {"m": ["a"]}}})
        second = request(path, {"command": "start", "options": {"only": {"m": ["b"]}}})
        assert first["ok"] is True, first
        assert second["ok"] is True, second
        assert first["journal"] != second["journal"]
        assert list(runtime.glob("labnotes/*.sock")) == [path]
        for _ in range(100):
            records = list(root.glob("exp/runs/*/run.json"))
            if len(records) == 2 and all(
                json.loads(record.read_text()).get("pid") for record in records
            ):
                break
            time.sleep(0.05)
        assert len(records) == 2
        plans = [
            json.loads(Path(str(answer["journal"])).read_text().splitlines()[0])
            for answer in (first, second)
        ]
        assert [plan["runs"][0]["params"]["m"] for plan in plans] == ["a", "b"]
        assert all(len(plan["runs"]) == 1 for plan in plans)
        assert request(path, {"command": "set_concurrency", "count": 2}) == {"ok": True}
        assert request(path, {"command": "restart", "options": {}})["ok"] is False
        assert request(path, {"command": "unknown"})["ok"] is False
        first_run = plans[0]["runs"][0]["run"]
        first_record = next(
            record for record in records if record.parent.name == first_run
        )
        second_record = next(record for record in records if record != first_record)
        assert request(path, {"command": "stop_one", "run": first_run}) == {"ok": True}
        for _ in range(100):
            if json.loads(first_record.read_text()).get("ended"):
                break
            time.sleep(0.05)
        assert json.loads(first_record.read_text())["ended_by"] == "stop"
        assert json.loads(second_record.read_text()).get("ended") is None
        assert request(path, {"command": "stop_all"}) == {"ok": True}
        for _ in range(100):
            if all(json.loads(record.read_text()).get("ended") for record in records):
                break
            time.sleep(0.05)
        assert all(
            json.loads(record.read_text())["ended_by"] == "stop" for record in records
        )
    finally:
        if daemon.poll() is None:
            daemon.terminate()
        daemon.communicate(timeout=15)


def test_restart_command_runs_a_failed_cell_again(
    tmp_path: Path, runtime: Path
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        "continues = false\n"
        "command = \"sh -c 'if test -f marker; then exit 0; else touch marker; exit 1; fi'\"\n"
    )
    env = {**os.environ, "XDG_RUNTIME_DIR": str(runtime)}
    daemon = subprocess.Popen(
        command(root, "daemon", "exp"), cwd=root, env=env, stdout=subprocess.PIPE
    )
    try:
        path = wait_for_socket(runtime)
        first = request(path, {"command": "start", "options": {}})
        assert first["ok"] is True, first
        for _ in range(100):
            records = list(root.glob("exp/runs/*/run.json"))
            if records and json.loads(records[0].read_text()).get("ended"):
                break
            time.sleep(0.05)
        assert len(records) == 1
        failed = json.loads(records[0].read_text())
        assert failed["exit_code"] == 1
        answer = request(
            path,
            {"command": "restart", "options": {"run_id": records[0].parent.name}},
        )
        assert answer["ok"] is True, answer
        assert answer["journal"] != first["journal"]
        for _ in range(100):
            records = list(root.glob("exp/runs/*/run.json"))
            if len(records) == 2 and all(
                json.loads(record.read_text()).get("ended") for record in records
            ):
                break
            time.sleep(0.05)
        assert len(records) == 2
        assert sorted(
            json.loads(record.read_text())["exit_code"] for record in records
        ) == [
            0,
            1,
        ]
    finally:
        if daemon.poll() is None:
            daemon.terminate()
        daemon.communicate(timeout=15)


def test_attach_connection_keeps_idle_daemon_alive_until_disconnect(
    tmp_path: Path, runtime: Path
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text("command = 'true'\n")
    env = {**os.environ, "XDG_RUNTIME_DIR": str(runtime)}
    daemon = subprocess.Popen(
        command(root, "daemon", "exp"), cwd=root, env=env, stdout=subprocess.PIPE
    )
    try:
        path = wait_for_socket(runtime)
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(5)
            client.connect(str(path))
            client.sendall(b'{"command":"attach"}\n')
            with client.makefile("r") as reply:
                assert json.loads(reply.readline()) == {"ok": True}
            time.sleep(5.5)
            assert daemon.poll() is None
        assert daemon.wait(timeout=10) == 0
        assert not path.exists()
    finally:
        if daemon.poll() is None:
            daemon.terminate()
        daemon.communicate(timeout=15)


def test_headless_flag_keeps_sighup_shutdown_in_foreground(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        "continues = false\n"
        f"command = \"{sys.executable} -c 'import time; time.sleep(600)'\"\n"
    )
    process = subprocess.Popen(
        command(root, "experiments", "exp", "run", "--headless"),
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for _ in range(100):
            records = list(root.glob("exp/runs/*/run.json"))
            if records and json.loads(records[0].read_text()).get("pid"):
                break
            time.sleep(0.05)
        assert records, "headless cell did not start"
        process.send_signal(signal.SIGHUP)
        output, _ = process.communicate(timeout=15)
        assert process.returncode == 0, output
        assert json.loads(records[0].read_text())["ended_by"] == "stop"
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
