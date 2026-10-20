import shlex
import sys
from pathlib import Path

import pytest
from curtaincall import expect

from labnotes.cli import main

TOO_LONG = Path("/tmp") / ("labnotes-unreachable-" * 8)
MISSING = Path("/tmp") / "labnotes-missing" / "nothing.sock"

PATCHED_CLI = f"""
import sys
from pathlib import Path

import labnotes.daemon.socket_path as module

module.socket_path = lambda root: Path({str(TOO_LONG)!r})

from labnotes.cli import main

sys.exit(main())
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


def test_exits_non_zero_when_the_daemon_socket_cannot_be_used(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "labnotes.daemon.daemon_running.socket_path", lambda root: TOO_LONG
    )

    assert run(make_project(tmp_path)) == 1

    out, err = capsys.readouterr()
    assert "passed" not in out
    assert_one_line_error(err, "AF_UNIX path too long")


def test_exits_non_zero_when_the_daemon_cannot_be_reached(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "labnotes.daemon.daemon_client.socket_path", lambda root: MISSING
    )

    assert run(make_project(tmp_path)) == 1

    out, err = capsys.readouterr()
    assert "passed" not in out
    assert_one_line_error(err, "No such file or directory")


def test_live_view_exits_non_zero_when_the_daemon_cannot_start(
    terminal, tmp_path: Path
) -> None:
    project = make_project(tmp_path)
    script = tmp_path / "patched_cli.py"
    script.write_text(PATCHED_CLI)
    config = project / ".labnotes.toml"
    term = terminal(
        f"{shlex.quote(sys.executable)} {script} -c {config} experiments exp run",
        rows=30,
        cols=120,
    )

    expect(term.get_by_text("AF_UNIX path too long")).to_be_visible()
    assert term.wait() == 1
    screen = term.to_snapshot()
    assert "Traceback" not in screen
    assert "passed" not in screen
