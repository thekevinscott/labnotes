import json
import os
import signal
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import psutil
import pytest
from curtaincall import expect

from conftest import Tui

VIEW = (
    "from textual.widgets import Static\n"
    "from labnotes.view import Changed\n"
    "class Progress(Static):\n"
    "    def on_labnotes_changed(self, message: Changed):\n"
    "        statuses = ' '.join(sorted(run['status'] for run in message.experiment.runs))\n"
    "        self.update(f'view runs: {len(message.experiment.runs)} {statuses}')\n"
)


def processes(root: Path, *words: str) -> list[psutil.Process]:
    config = str(root / ".labnotes.toml")
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (cmdline := process.info["cmdline"] or [])
        and all(word in cmdline for word in words)
    ]


def inotify_watches(process: psutil.Process) -> int:
    watches = 0
    for fd in os.listdir(f"/proc/{process.pid}/fd"):
        try:
            if os.readlink(f"/proc/{process.pid}/fd/{fd}") != "anon_inode:inotify":
                continue
            info = Path(f"/proc/{process.pid}/fdinfo/{fd}").read_text()
        except FileNotFoundError:
            continue
        watches += sum(line.startswith("inotify wd:") for line in info.splitlines())
    return watches


def wait_for(check, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.05)
    raise AssertionError("condition did not hold in time")


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        yield Path(folder)


@pytest.fixture
def root(tmp_path: Path) -> Iterator[Path]:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / "data/a/b/c").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "progress.py").write_text(VIEW)
    (root / "hold.py").write_text(
        "import time\nfrom pathlib import Path\n"
        f"while not Path({str(root / 'release')!r}).exists():\n    time.sleep(0.05)\n"
    )
    yield root
    (root / "release").write_text("")


def configure(root: Path, command: str) -> None:
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} {command}"\ncontinues = false\n'
        '[views]\nprogress = "progress.py:Progress"\n'
    )


def test_installed_tuis_read_views_from_the_daemon_and_hold_no_watches(
    root: Path, tui: Tui, runtime: Path
) -> None:
    configure(root, "hold.py")
    env = {"XDG_RUNTIME_DIR": str(runtime)}
    run = tui(root, "experiments", "exp", "run", env=env, cols=160)
    expect(run.get_by_text("1 at a time")).to_be_visible(timeout=60)
    run.write("2")
    expect(run.get_by_text("view runs: 1 running")).to_be_visible(timeout=30)
    wait_for(lambda: len(processes(root, "daemon")) == 1)
    [daemon] = processes(root, "daemon")
    before = inotify_watches(daemon)

    attached = tui(root, "experiments", "exp", "attach", env=env, cols=160)
    expect(attached.get_by_text("1 at a time")).to_be_visible(timeout=60)
    attached.write("2")
    expect(attached.get_by_text("view runs: 1 running")).to_be_visible(timeout=30)

    tuis = processes(root, "experiments")
    assert len(tuis) >= 2
    assert [inotify_watches(found) for found in tuis] == [0] * len(tuis)
    assert inotify_watches(daemon) == before

    (root / "release").write_text("")
    for term in (run, attached):
        expect(term.get_by_text("view runs: 1 passed")).to_be_visible(timeout=30)
        tui.quit(term)


def test_installed_tui_starts_a_daemon_when_its_idle_daemon_is_gone(
    root: Path, tui: Tui, runtime: Path
) -> None:
    configure(root, "-c pass")
    env = {"XDG_RUNTIME_DIR": str(runtime)}
    term = tui(root, "experiments", "exp", "run", env=env, cols=160)
    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=60)
    term.write("2")
    expect(term.get_by_text("view runs: 1 passed")).to_be_visible(timeout=30)
    wait_for(lambda: len(processes(root, "daemon")) == 1)
    [lost] = processes(root, "daemon")
    lost.send_signal(signal.SIGKILL)
    psutil.wait_procs([lost], timeout=10)

    wait_for(lambda: [p.pid for p in processes(root, "daemon")] not in ([], [lost.pid]))
    later = root / "exp/runs/20261116-000000-later"
    later.mkdir(parents=True)
    (later / "run.json").write_text(
        json.dumps(
            {
                "params": {},
                "created": "2026-11-16T00:00:00Z",
                "ended": "2026-11-16T00:00:01Z",
                "exit_code": 0,
            }
        )
    )
    expect(term.get_by_text("view runs: 2 passed passed")).to_be_visible(timeout=30)
    expect(term.get_by_text("Lost the daemon")).not_to_be_visible()
    tui.quit(term)
