import json
import os
import shlex
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import psutil
import pytest

SCRIPT = """
import json
import os
import sys
import time
from pathlib import Path

value = sys.argv[sys.argv.index("--m") + 1]
token = sys.argv[sys.argv.index("--token") + 1] if "--token" in sys.argv else None
with Path("launches.jsonl").open("a") as log:
    log.write(json.dumps({
        "m": value,
        "token": token,
        "probe": os.environ.get("RESTART_PROBE"),
        "config": sys.argv[1],
    }) + "\\n")
if value == "hold":
    for _ in range(1200):
        if Path("release").exists():
            break
        time.sleep(0.05)
if value == "a" and Path("fail-once").exists():
    Path("fail-once").unlink()
    sys.exit(1)
"""


@pytest.fixture(autouse=True)
def cleanup_daemons(tmp_path: Path) -> Iterator[None]:
    yield
    (tmp_path / "project" / "release").write_text("")
    config = str(tmp_path / "project" / ".labnotes.toml")
    owners = [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (process.info["cmdline"] or [])
        and "daemon" in (process.info["cmdline"] or [])
    ]
    for process in owners:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(owners, timeout=15)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        yield Path(folder)


def project(root: Path) -> Path:
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(SCRIPT)
    (root / "fail-once").write_text("")
    for name, path in (("default", "exp/experiment.toml"), ("other", "other.toml")):
        (root / path).write_text(
            f'command = "{sys.executable} script.py {name}"\n'
            "continues = false\nretries = 0\nconcurrency = 2\n"
            '[params]\nm = ["a", "hold"]\n'
        )
    return root


def labnotes(root: Path, *args: str) -> list[str]:
    return [
        str(Path(sys.executable).parent / "labnotes"),
        "-c",
        str(root / ".labnotes.toml"),
        *args,
    ]


def launches(root: Path) -> list[dict[str, object]]:
    log = root / "launches.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines()]


def records(root: Path) -> dict[str, dict[str, object]]:
    return {
        path.parent.name: json.loads(path.read_text())
        for path in (root / "exp/runs").rglob("run.json")
    }


def wait_for(check, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.05)
    raise AssertionError("condition did not hold in time")


def failed_run(root: Path) -> str:
    wait_for(
        lambda: any(record.get("exit_code") == 1 for record in records(root).values())
    )
    wait_for(lambda: any(launch["m"] == "hold" for launch in launches(root)))
    [failed] = [
        run for run, record in records(root).items() if record.get("exit_code") == 1
    ]
    return failed


def daemon_from_another_shell(
    root: Path, runtime: Path
) -> tuple[subprocess.Popen[bytes], socket.socket]:
    env = {**os.environ, "XDG_RUNTIME_DIR": str(runtime), "RESTART_PROBE": "daemon"}
    daemon = subprocess.Popen(labnotes(root, "daemon", "exp"), cwd=root, env=env)
    wait_for(lambda: bool(list(runtime.glob("labnotes/*.sock"))))
    [path] = runtime.glob("labnotes/*.sock")
    attached = socket.socket(socket.AF_UNIX)
    attached.connect(str(path))
    attached.sendall(b'{"command":"attach"}\n')
    return daemon, attached


def screen(term) -> str:
    return "\n".join("".join(row) for row in term.get_viewable_buffer())


def restart(term, root: Path, run: str) -> dict[str, object]:
    wait_for(lambda: run in screen(term))
    rows = screen(term).splitlines()
    target = next(i for i, row in enumerate(rows) if run in row)
    others = [
        i
        for i, row in enumerate(rows)
        if any(other in row for other in records(root) if other != run)
    ]
    if others and others[0] < target:
        term.key_down()
    # The live view may not have seen the failure yet; it says so and does nothing.
    for _ in range(30):
        term.write("r")
        wait_for(
            lambda: "Restarted" in screen(term) or "has not failed" in screen(term)
        )
        if "Restarted" in screen(term):
            break
        time.sleep(0.5)
    wait_for(lambda: len(launches(root)) == 3)
    return launches(root)[2]


def test_live_run_restart_sends_this_shells_environment_and_config(
    terminal, tmp_path: Path, runtime: Path
) -> None:
    root = project(tmp_path / "project")
    daemon, attached = daemon_from_another_shell(root, runtime)
    try:
        term = terminal(
            shlex.join(
                labnotes(
                    root, "experiments", "exp", "run", "-e", str(root / "other.toml")
                )
                + ["--", "--token", "original"]
            ),
            rows=30,
            cols=200,
            env={
                **os.environ,
                "XDG_RUNTIME_DIR": str(runtime),
                "RESTART_PROBE": "client",
            },
        )
        failed = failed_run(root)

        restarted = restart(term, root, failed)

        assert restarted == {
            "m": "a",
            "token": "original",
            "probe": "client",
            "config": "other",
        }
    finally:
        (root / "release").write_text("")
        attached.close()
        daemon.terminate()
