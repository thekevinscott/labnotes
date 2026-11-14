import asyncio
import fcntl
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import pytest
import psutil

from conftest import DaemonEvents, daemon_request
from labnotes.daemon.client import daemon_socket
from labnotes.daemon.ensure import ensure_daemon
from labnotes.daemon.socket_path import lock_path
from labnotes.read_config import read_config


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        yield Path(folder)


@pytest.fixture
def runtime_env(runtime: Path) -> Iterator[Path]:
    with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(runtime)}):
        yield runtime


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


def test_concurrent_starters_reuse_one_daemon(
    tmp_path: Path, runtime_env: Path
) -> None:
    runtime = runtime_env
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    config_path = root / ".labnotes.toml"
    config_path.write_text("")
    (root / "exp/experiment.toml").write_text("command = 'true'\n")
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


def test_stop_command_stops_a_running_cell(tmp_path: Path, runtime: Path) -> None:
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
        answer = daemon_request(path, "POST", "/start", {})
        assert answer["ok"] is True, answer
        assert answer["batch"]
        for _ in range(100):
            records = list(root.glob("exp/runs/*/run.json"))
            if records and json.loads(records[0].read_text()).get("pid"):
                break
            time.sleep(0.05)
        assert records, "cell did not start"
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


def test_two_starts_share_one_daemon_and_keep_batches_separate(
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
        first = daemon_request(path, "POST", "/start", {"only": {"m": ["a"]}})
        second = daemon_request(path, "POST", "/start", {"only": {"m": ["b"]}})
        assert first["ok"] is True, first
        assert second["ok"] is True, second
        assert first["batch"] != second["batch"]
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
            json.loads(record.read_text())
            for record in sorted(
                records,
                key=lambda record: json.loads(record.read_text())["params"]["m"],
            )
        ]
        assert [plan["params"]["m"] for plan in plans] == ["a", "b"]
        assert daemon_request(path, "POST", "/concurrency", {"count": 2}) == {
            "ok": True
        }
        assert daemon_request(path, "POST", "/restart", {})["ok"] is False
        assert daemon_request(path, "POST", "/concurrency", {"count": 0})["ok"] is False
        first_run = next(
            record.parent.name
            for record in records
            if json.loads(record.read_text())["params"]["m"] == "a"
        )
        first_record = next(
            record for record in records if record.parent.name == first_run
        )
        second_record = next(record for record in records if record != first_record)
        assert daemon_request(path, "POST", f"/runs/{first_run}/stop") == {"ok": True}
        for _ in range(100):
            if json.loads(first_record.read_text()).get("ended"):
                break
            time.sleep(0.05)
        assert json.loads(first_record.read_text())["ended_by"] == "stop"
        assert json.loads(second_record.read_text()).get("ended") is None
        assert daemon_request(path, "POST", "/stop") == {"ok": True}
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
        first = daemon_request(path, "POST", "/start", {})
        assert first["ok"] is True, first
        for _ in range(100):
            records = list(root.glob("exp/runs/*/run.json"))
            if records and json.loads(records[0].read_text()).get("ended"):
                break
            time.sleep(0.05)
        assert len(records) == 1
        failed = json.loads(records[0].read_text())
        assert failed["exit_code"] == 1
        answer = daemon_request(
            path, "POST", "/restart", {"run_id": records[0].parent.name}
        )
        assert answer["ok"] is True, answer
        assert answer["batch"] != first["batch"]
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
        with DaemonEvents(path) as events:
            assert events.batches == []
            time.sleep(5.5)
            assert daemon.poll() is None
        assert daemon.wait(timeout=10) == 0
        assert not path.exists()
    finally:
        if daemon.poll() is None:
            daemon.terminate()
        daemon.communicate(timeout=15)


def test_run_without_tty_reports_usage_without_starting_daemon(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text("continues = false\ncommand = 'true'\n")
    result = subprocess.run(
        command(root, "experiments", "exp", "run"),
        cwd=root,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "run requires a terminal" in result.stderr
    assert not list(root.glob("exp/runs/*/run.json"))


def test_two_starts_do_not_exceed_repeats_on_one_daemon(
    tmp_path: Path, runtime: Path
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        "continues = false\nrepeats = 3\nconcurrency = 2\n"
        f"command = \"{sys.executable} -c 'import time; time.sleep(4)'\"\n"
    )
    env = {**os.environ, "XDG_RUNTIME_DIR": str(runtime)}
    daemon = subprocess.Popen(
        command(root, "daemon", "exp"), cwd=root, env=env, stdout=subprocess.PIPE
    )
    try:
        path = wait_for_socket(runtime)
        first = daemon_request(path, "POST", "/start", {})
        second = daemon_request(path, "POST", "/start", {})
        assert first["ok"] is True, first
        assert second["ok"] is True, second
        for _ in range(200):
            if daemon_request(path, "GET", "/batches") == {"ok": True, "batches": []}:
                break
            time.sleep(0.05)
        records = list(root.glob("exp/runs/*/run.json"))
        assert len(records) == 3, records
        assert all(json.loads(p.read_text()).get("ended") for p in records), records
    finally:
        if daemon.poll() is None:
            daemon.terminate()
        daemon.communicate(timeout=15)
