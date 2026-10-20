import os
import shlex
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest
from curtaincall import expect

from labnotes.cli import main
from labnotes.daemon.socket_path import socket_path

UNUSED_UID = 2_000_000_000 + os.getpid()

HANG_UP = """
import socket
import sys

server = socket.socket(socket.AF_UNIX)
server.bind(sys.argv[1])
server.listen()
while True:
    client, _ = server.accept()
    client.recv(65536)
    client.close()
"""


def make_project(root: Path) -> Path:
    (root / ".labnotes.toml").write_text("")
    (root / "exp").mkdir()
    (root / "exp" / "experiment.toml").write_text(
        f"command = '{sys.executable} -c pass'\n"
    )
    return root


def run(project: Path) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(project / ".labnotes.toml"), "experiments", "exp", "run"])
    return exit_info.value.code


def assert_one_line_error(err: str, cause: str) -> None:
    lines = err.strip().splitlines()
    assert len(lines) == 1, err
    assert lines[0].startswith("Error: ")
    assert cause in lines[0]


@pytest.fixture
def blocked_socket_folder() -> Iterator[Path]:
    folder = Path("/tmp") / f"labnotes-{UNUSED_UID}"
    folder.write_text("not a folder")
    try:
        with mock.patch("os.getuid", return_value=UNUSED_UID):
            yield folder
    finally:
        folder.unlink()


@pytest.fixture
def hanging_up_daemon(tmp_path: Path) -> Iterator[Path]:
    project = make_project(tmp_path)
    path = socket_path(project)
    server = subprocess.Popen([sys.executable, "-c", HANG_UP, str(path)])
    try:
        while not path.exists():
            time.sleep(0.05)
        yield project
    finally:
        server.kill()
        server.wait()
        path.unlink()


def test_exits_non_zero_when_the_daemon_socket_cannot_be_made(
    tmp_path: Path, blocked_socket_folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(make_project(tmp_path)) == 1

    out, err = capsys.readouterr()
    assert "passed" not in out
    assert_one_line_error(err, f"File exists: '{blocked_socket_folder}'")


def test_exits_non_zero_when_the_daemon_hangs_up(
    hanging_up_daemon: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(hanging_up_daemon) == 1

    out, err = capsys.readouterr()
    assert "passed" not in out
    assert_one_line_error(err, "Can't reach the labnotes daemon: ")


def test_live_view_exits_non_zero_when_the_daemon_hangs_up(
    terminal, hanging_up_daemon: Path
) -> None:
    labnotes = Path(sys.executable).parent / "labnotes"
    config = hanging_up_daemon / ".labnotes.toml"
    term = terminal(
        f"{shlex.quote(str(labnotes))} -c {config} experiments exp run",
        rows=30,
        cols=120,
    )

    expect(term.get_by_text("Can't reach the labnotes daemon")).to_be_visible()
    assert term.wait() == 1
    screen = term.to_snapshot()
    assert "Traceback" not in screen
    assert "passed" not in screen
