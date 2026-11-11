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
from curtaincall import expect

# Records every stdout/stderr log a run TUI process opens. The daemon and the
# run's own child are excluded by argv, so only the TUI is checked.
RECORD_OPENS = """
import os, sys

def _record(event, args):
    if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    argv = sys.argv
    if "daemon" in argv or "experiments" not in argv:
        return
    path = os.fsdecode(args[0])
    name = os.path.basename(path)
    if "/runs/" in path and name.startswith(("stdout", "stderr")):
        with open(os.environ["LABNOTES_TEST_OPENS"], "a") as found:
            found.write(path + "\\n")

sys.addaudithook(_record)
"""


@pytest.fixture(autouse=True)
def cleanup_daemons(tmp_path: Path) -> Iterator[None]:
    yield
    owners = [
        process
        for process in psutil.process_iter(["cmdline"])
        if "daemon" in (cmdline := process.info["cmdline"] or [])
        and any(str(tmp_path) in part for part in cmdline)
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


def labnotes(root: Path, *args: str) -> list[str]:
    return [
        str(Path(sys.executable).parent / "labnotes"),
        "-c",
        str(root / ".labnotes.toml"),
        *args,
    ]


def wait_for_socket(runtime: Path) -> Path:
    for _ in range(100):
        if sockets := list(runtime.glob("labnotes/*.sock")):
            return sockets[0]
        time.sleep(0.05)
    raise AssertionError("daemon socket did not appear")


def request(path: Path, message: dict[str, object]) -> dict[str, object]:
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(10)
        client.connect(str(path))
        client.sendall((json.dumps(message) + "\n").encode())
        with client.makefile("r") as replies:
            for line in replies:
                reply = json.loads(line)
                if "step" not in reply:
                    return reply
    raise AssertionError("daemon closed without a reply")


def test_attached_client_receives_live_stdout_and_stderr(
    tmp_path: Path, runtime: Path
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    release = root / "release"
    script = (
        "import sys, time\nfrom pathlib import Path\n"
        "print('live-out-7731', flush=True)\n"
        "print('live-err-4419', file=sys.stderr, flush=True)\n"
        f"while not Path({str(release)!r}).exists(): time.sleep(0.05)\n"
    )
    (root / "child.py").write_text(script)
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} child.py"\n'
    )
    env = {**os.environ, "XDG_RUNTIME_DIR": str(runtime)}
    daemon = subprocess.Popen(
        labnotes(root, "daemon", "exp"), cwd=root, env=env, stdout=subprocess.PIPE
    )
    try:
        path = wait_for_socket(runtime)
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(10)
            client.connect(str(path))
            client.sendall(b'{"command":"attach"}\n')
            received = b""
            while b"\n" not in received:
                received += client.recv(65536)
            reply, _, received = received.partition(b"\n")
            assert json.loads(reply).get("ok") is True

            started = request(path, {"command": "start", "options": {}})
            assert started["ok"] is True, started

            deadline = time.monotonic() + 15
            client.settimeout(0.5)
            while time.monotonic() < deadline and not (
                b"live-out-7731" in received and b"live-err-4419" in received
            ):
                try:
                    chunk = client.recv(65536)
                except TimeoutError:
                    continue
                if not chunk:
                    break
                received += chunk
            # The child is still blocked on the release file, so anything
            # seen here arrived while the run was live.
            seen = received.decode("utf-8", "replace")
            assert "live-out-7731" in seen, seen
            assert "live-err-4419" in seen, seen
            release.write_text("")
        [record] = root.glob("exp/runs/*/stdout.log")
        assert "live-out-7731" in record.read_text()
    finally:
        release.write_text("")
        if daemon.poll() is None:
            daemon.terminate()
        daemon.communicate(timeout=30)


# The views path opens dirsql tables and a run_files watcher; the plain path
# polls the files. Both must take logs from the daemon.
@pytest.mark.parametrize("views", [False, True], ids=["plain", "views"])
def test_run_tui_shows_live_output_without_reading_log_files(
    terminal, tmp_path: Path, views: bool
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    command = (
        f"{shlex.quote(sys.executable)} -c "
        "\"import sys, time\nfor i in range(100): print('tick', i, flush=True); "
        "print('warn', i, file=sys.stderr, flush=True); "
        'time.sleep(0.2)"'
    )
    config = f"continues = false\ncommand = '''{command}'''\n"
    if views:
        config += '[views]\nprogress = "progress.py:Progress"\n'
        (root / "progress.py").write_text(
            "from textual.widgets import Static\nclass Progress(Static):\n    pass\n"
        )
    (root / "exp/experiment.toml").write_text(config)
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "sitecustomize.py").write_text(RECORD_OPENS)
    opens = tmp_path / "opens.txt"
    labnotes_bin = Path(sys.executable).parent / "labnotes"
    term = terminal(
        f"{labnotes_bin} -c {root / '.labnotes.toml'} experiments exp run",
        rows=30,
        cols=120,
        env={"PYTHONPATH": str(hooks), "LABNOTES_TEST_OPENS": str(opens)},
    )
    expect(term.get_by_text("1 at a time")).to_be_visible(timeout=30)
    term.key_enter()
    expect(term.get_by_text("tick 3")).to_be_visible()
    expect(term.get_by_text("tick 12")).to_be_visible()
    term.write("t")
    expect(term.get_by_text("warn 20")).to_be_visible()
    term.key_ctrl_c()
    expect(term.get_by_text("leave running")).to_be_visible()
    term.write("s")
    term.wait()

    assert list(root.glob("exp/runs/*/stdout.log")), "run wrote no log record"
    read = opens.read_text().splitlines() if opens.exists() else []
    assert read == [], f"run TUI read log files itself: {sorted(set(read))}"


def test_log_files_stay_complete_while_an_attached_client_stalls(
    tmp_path: Path, runtime: Path
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "child.py").write_text(
        "import sys\n"
        "for i in range(200_000):\n"
        "    print(f'out {i:06d} ' + 'x' * 40)\n"
        "    if i % 1000 == 0: print(f'err {i:06d}', file=sys.stderr)\n"
    )
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} child.py"\n'
    )
    env = {**os.environ, "XDG_RUNTIME_DIR": str(runtime)}
    daemon = subprocess.Popen(
        labnotes(root, "daemon", "exp"), cwd=root, env=env, stdout=subprocess.PIPE
    )
    try:
        path = wait_for_socket(runtime)
        with socket.socket(socket.AF_UNIX) as stalled:
            stalled.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            stalled.connect(str(path))
            stalled.sendall(b'{"command":"attach"}\n')
            started = request(path, {"command": "start", "options": {}})
            assert started["ok"] is True, started
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                ended = [
                    record
                    for record in root.glob("exp/runs/*/run.json")
                    if json.loads(record.read_text()).get("ended")
                ]
                if ended:
                    break
                time.sleep(0.1)
            assert ended, "a client that never reads held the run back"
        [folder] = root.glob("exp/runs/*")
        expected_out = "".join(
            f"out {i:06d} " + "x" * 40 + "\n" for i in range(200_000)
        )
        expected_err = "".join(f"err {i:06d}\n" for i in range(0, 200_000, 1000))
        assert (folder / "stdout.log").read_text() == expected_out
        assert (folder / "stderr.log").read_text() == expected_err
        assert json.loads((folder / "run.json").read_text())["exit_code"] == 0
    finally:
        if daemon.poll() is None:
            daemon.terminate()
        daemon.communicate(timeout=30)
