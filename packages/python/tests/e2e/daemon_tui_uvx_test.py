import json
import shlex

from curtaincall import Terminal, expect
import os
import signal
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import psutil
import pytest


@pytest.fixture(autouse=True)
def cleanup_daemons(tmp_path: Path) -> Iterator[None]:
    yield
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


def signal_tui(term: Terminal, number: int) -> None:
    # Curtaincall has no public signal API; keep terminal I/O and assertions there.
    assert term._child is not None
    os.killpg(term._child.pid, number)


def test_uvx_tui_crash_keeps_run_alive(
    terminal, tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = \"{sys.executable} -c 'import time; print(12345, flush=True); time.sleep(6)'\"\n"
    )
    command = shlex.join(
        ["uvx", "labnotes", "-c", str(root / ".labnotes.toml"), "experiments", "exp"]
    )
    term = terminal(command + " run", rows=30, cols=160, env={**os.environ, **uvx})
    expect(term.get_by_text("12345")).to_be_visible(timeout=30)
    expect(term.get_by_text("1 at a time")).to_be_visible()
    signal_tui(term, signal.SIGKILL)
    term.wait(timeout=10)
    for _ in range(200):
        [path] = root.glob("exp/runs/*/run.json")
        if json.loads(path.read_text()).get("ended"):
            break
        time.sleep(0.05)
    assert json.loads(path.read_text())["exit_code"] == 0
    browser = terminal(command, rows=30, cols=160, env={**os.environ, **uvx})
    expect(browser.get_by_text(path.parent.name)).to_be_visible(timeout=30)
    browser.key_enter()
    expect(browser.get_by_text("12345")).to_be_visible()
    browser.key_ctrl_c()
    assert browser.wait() == 0


def test_uvx_frozen_tui_keeps_scheduling(
    terminal, tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\nrepeats = 2\n"
        f"command = \"{sys.executable} -c 'import time; print(12345, flush=True); time.sleep(3)'\"\n"
    )
    term = terminal(
        shlex.join(
            [
                "uvx",
                "labnotes",
                "-c",
                str(root / ".labnotes.toml"),
                "experiments",
                "exp",
                "run",
            ]
        ),
        rows=30,
        cols=160,
        env={**os.environ, **uvx},
    )
    expect(term.get_by_text("12345")).to_be_visible(timeout=30)
    expect(term.get_by_text("1 at a time")).to_be_visible()
    signal_tui(term, signal.SIGSTOP)
    try:
        for _ in range(200):
            paths = list(root.glob("exp/runs/*/run.json"))
            if len(paths) == 2 and all(
                json.loads(path.read_text()).get("ended") for path in paths
            ):
                break
            time.sleep(0.05)
        assert len(paths) == 2
        assert all(json.loads(path.read_text())["exit_code"] == 0 for path in paths)
    finally:
        signal_tui(term, signal.SIGCONT)
    expect(term.get_by_text("2 passed, 0 failed.")).to_be_visible(timeout=15)
    term.key_ctrl_c()
    assert term.wait() == 0


def test_uvx_browse_restart_survives_tui_kill(
    terminal, tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "marker").write_text("")
    (root / "script.py").write_text(
        "import sys, time\nfrom pathlib import Path\n"
        "if Path('marker').exists():\n    Path('marker').unlink()\n    sys.exit(1)\n"
        "print('restart running', flush=True)\ntime.sleep(3)\n"
    )
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\ncontinues = false\nretries = 0\n'
    )
    command = shlex.join(
        ["uvx", "labnotes", "-c", str(root / ".labnotes.toml"), "experiments", "exp"]
    )
    first = terminal(command + " run", rows=30, cols=160, env={**os.environ, **uvx})
    expect(first.get_by_text("0 passed, 1 failed.")).to_be_visible(timeout=30)
    first.key_ctrl_c()
    assert first.wait() == 0
    [failed] = root.glob("exp/runs/*/run.json")
    browser = terminal(command, rows=30, cols=160, env={**os.environ, **uvx})
    expect(browser.get_by_text(failed.parent.name)).to_be_visible(timeout=30)
    browser.write("r")
    expect(browser.get_by_text("Restarted")).to_be_visible(timeout=30)
    signal_tui(browser, signal.SIGKILL)
    browser.wait(timeout=10)
    for _ in range(200):
        paths = list(root.glob("exp/runs/*/run.json"))
        if len(paths) == 2 and all(
            json.loads(path.read_text()).get("ended") for path in paths
        ):
            break
        time.sleep(0.05)
    assert sorted(json.loads(path.read_text())["exit_code"] for path in paths) == [0, 1]
    [restarted] = [path for path in paths if path != failed]
    reopened = terminal(command, rows=30, cols=160, env={**os.environ, **uvx})
    expect(reopened.get_by_text(restarted.parent.name)).to_be_visible(timeout=30)
    reopened.key_ctrl_c()
    assert reopened.wait() == 0


def test_uvx_second_tty_reuses_daemon_then_idle_daemon_exits(
    terminal, tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = \"{sys.executable} -c 'import time; time.sleep(3)'\"\n"
    )
    command = shlex.join(
        [
            "uvx",
            "labnotes",
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
        ]
    )
    with TemporaryDirectory(prefix="ln-runtime-") as runtime:
        env = {**os.environ, **uvx, "XDG_RUNTIME_DIR": runtime}
        first = terminal(command, rows=30, cols=160, env=env)
        expect(first.get_by_text("1 at a time")).to_be_visible(timeout=30)
        [path] = Path(runtime).glob("labnotes/*.sock")
        second = terminal(command, rows=30, cols=160, env=env)
        expect(second.get_by_text("0 passed, 0 failed.")).to_be_visible(timeout=30)
        expect(first.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=15)
        assert list(Path(runtime).glob("labnotes/*.sock")) == [path]
        time.sleep(5.5)
        assert path.exists()
        first.key_ctrl_c()
        second.key_ctrl_c()
        assert first.wait() == 0
        assert second.wait() == 0
        for _ in range(150):
            if not path.exists():
                break
            time.sleep(0.05)
        assert not path.exists()
