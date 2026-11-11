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

from curtaincall import expect
import psutil
import pytest

SCRIPT = """
import sys, time
from pathlib import Path

value = sys.argv[sys.argv.index("--m") + 1]
with Path("launches").open("a") as log:
    log.write(value + "\\n")
if value == "a" and Path("fail-once").exists():
    Path("fail-once").unlink()
    sys.exit(1)
for _ in range(1200):
    if Path("release").exists():
        break
    time.sleep(0.05)
"""


def daemons(root: Path) -> list[psutil.Process]:
    config = str(root / ".labnotes.toml")
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (process.info["cmdline"] or [])
        and "daemon" in (process.info["cmdline"] or [])
    ]


@pytest.fixture(autouse=True)
def cleanup_daemons(tmp_path: Path) -> Iterator[None]:
    yield
    (tmp_path / "release").write_text("")
    owners = daemons(tmp_path)
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
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\n'
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


def wait_for(check, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.05)
    raise AssertionError("condition did not hold in time")


def launches(root: Path) -> list[str]:
    log = root / "launches"
    return log.read_text().splitlines() if log.exists() else []


def send(runtime: Path, message: dict[str, object]) -> dict[str, object]:
    [path] = runtime.glob("labnotes/*.sock")
    with socket.socket(socket.AF_UNIX) as client:
        client.connect(str(path))
        client.sendall((json.dumps(message) + "\n").encode())
        with client.makefile("r") as replies:
            for line in replies:
                reply = json.loads(line)
                if "step" not in reply:
                    return reply  # type: ignore[no-any-return]
    raise AssertionError("daemon closed without a reply")


def failed_run(root: Path) -> str:
    def failed() -> list[str]:
        return [
            path.parent.name
            for path in root.glob("exp/runs/*/run.json")
            if json.loads(path.read_text()).get("exit_code") == 1
        ]

    wait_for(lambda: bool(failed()))
    return failed()[0]


def test_attach_with_nothing_running_says_so_and_starts_nothing(
    terminal, tmp_path: Path, runtime: Path
) -> None:
    root = project(tmp_path)

    term = terminal(
        shlex.join(labnotes(root, "experiments", "exp", "attach")),
        rows=30,
        cols=120,
        env={**os.environ, "XDG_RUNTIME_DIR": str(runtime)},
    )

    expect(term.get_by_text("Nothing is running for exp.")).to_be_visible(timeout=15)
    assert term.wait(timeout=10) == 0
    assert not daemons(root)
    assert not list(runtime.glob("labnotes/*.sock"))
    assert not list(root.glob("exp/runs/*"))


def test_several_attached_tuis_follow_the_batch_and_its_restart(
    terminal, tmp_path: Path, runtime: Path
) -> None:
    root = project(tmp_path)
    env = {**os.environ, "XDG_RUNTIME_DIR": str(runtime)}
    daemon = subprocess.Popen(labnotes(root, "daemon", "exp"), cwd=root, env=env)
    wait_for(lambda: bool(list(runtime.glob("labnotes/*.sock"))))
    try:
        assert send(runtime, {"command": "start", "options": {}})["ok"] is True
        failed = failed_run(root)
        wait_for(lambda: "hold" in launches(root))
        terms = [
            terminal(
                shlex.join(labnotes(root, "experiments", "exp", "attach")),
                rows=30,
                cols=200,
                env=env,
            )
            for _ in range(2)
        ]
        for term in terms:
            expect(term.get_by_text("✗ exited 1")).to_be_visible(timeout=30)

        reply = send(runtime, {"command": "restart", "options": {"run_id": failed}})
        assert reply["ok"] is True
        wait_for(lambda: len(launches(root)) == 3)
        [restarted] = [
            path.parent.name
            for path in root.glob("exp/runs/*/run.json")
            if json.loads(path.read_text()).get("retry_of") == failed
        ]
        for term in terms:
            expect(term.get_by_text(restarted)).to_be_visible(timeout=30)
        (root / "release").write_text("")

        for term in terms:
            expect(term.get_by_text("2 passed, 0 failed. 1 retried.")).to_be_visible(
                timeout=30
            )
            term.key_ctrl_c()
            assert term.wait(timeout=10) == 0
    finally:
        (root / "release").write_text("")
        daemon.terminate()
        daemon.wait(timeout=15)
