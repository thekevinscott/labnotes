import json
import re
import signal
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from curtaincall import expect

from conftest import Tui


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        yield Path(folder)


def wait_for(check, seconds: float = 15) -> None:
    deadline = time.monotonic() + seconds
    while not check() and time.monotonic() < deadline:
        time.sleep(0.05)


def records(root: Path) -> list[dict]:
    return [json.loads(path.read_text()) for path in root.glob("exp/runs/*/run.json")]


def test_uvx_tui_crash_keeps_run_alive(tmp_path: Path, tui: Tui, runtime: Path) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        "continues = false\n"
        f"command = \"{sys.executable} -c 'print(12345, flush=True); "
        "import time; time.sleep(6)'\"\n"
    )
    env = {"XDG_RUNTIME_DIR": str(runtime)}
    term = tui(root, "experiments", "exp", "run", env=env, cols=160)
    expect(term.get_by_text("12345")).to_be_visible(timeout=60)
    assert list(runtime.glob("labnotes/*.sock"))
    tui.signal(term, signal.SIGKILL)
    expect(term).to_have_exited(timeout=10)

    wait_for(lambda: all(record.get("ended") for record in records(root)))
    [record] = records(root)
    assert record["exit_code"] == 0
    [folder] = root.glob("exp/runs/*")
    browser = tui(root, "experiments", "exp", env=env, cols=160)
    expect(browser.get_by_text(folder.name)).to_be_visible(timeout=60)
    browser.key_enter()
    expect(browser.get_by_text("12345")).to_be_visible()
    tui.quit(browser)


def test_uvx_frozen_tui_keeps_scheduling(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        "continues = false\nrepeats = 2\n"
        f"command = \"{sys.executable} -c 'print(12345, flush=True); "
        "import time; time.sleep(3)'\"\n"
    )
    term = tui(root, "experiments", "exp", "run", cols=160)
    expect(term.get_by_text(re.compile(r"[|/\\-] +\d+s"))).to_be_visible(timeout=60)
    tui.signal(term, signal.SIGSTOP)
    try:
        wait_for(
            lambda: len(found := records(root)) == 2
            and all(record.get("ended") for record in found),
            seconds=20,
        )
        found = records(root)
        assert len(found) == 2
        assert all(record["exit_code"] == 0 for record in found)
    finally:
        tui.signal(term, signal.SIGCONT)
    expect(term.get_by_text("2 passed, 0 failed.")).to_be_visible(timeout=15)
    term.write("/")
    expect(term.get_by_text("Filter params")).to_be_visible()
    term.key_escape()
    expect(term.get_by_text("Filter params")).not_to_be_visible()
    # Ctrl-C after SIGSTOP/SIGCONT sometimes leaves the TUI open, so kill it.
    tui.check(term)
    tui.signal(term, signal.SIGKILL)


def test_uvx_browse_restart_survives_tui_kill(tmp_path: Path, tui: Tui) -> None:
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
    first = tui(root, "experiments", "exp", "run", cols=160)
    expect(first.get_by_text("0 passed, 1 failed.")).to_be_visible(timeout=60)
    tui.quit(first)
    [failed] = root.glob("exp/runs/*/run.json")

    browser = tui(root, "experiments", "exp", cols=160)
    expect(browser.get_by_text(failed.parent.name)).to_be_visible(timeout=60)
    browser.write("r")
    expect(browser.get_by_text("Restarted")).to_be_visible(timeout=30)
    tui.signal(browser, signal.SIGKILL)
    expect(browser).to_have_exited(timeout=10)

    wait_for(
        lambda: len(found := records(root)) == 2
        and all(record.get("ended") for record in found)
    )
    assert sorted(record["exit_code"] for record in records(root)) == [0, 1]
    [restarted] = [path for path in root.glob("exp/runs/*/run.json") if path != failed]
    reopened = tui(root, "experiments", "exp", cols=160)
    expect(reopened.get_by_text(restarted.parent.name)).to_be_visible(timeout=60)
    tui.quit(reopened)


def test_uvx_second_tty_reuses_daemon_then_idle_daemon_exits(
    tmp_path: Path, tui: Tui, runtime: Path
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        "continues = false\n"
        f"command = \"{sys.executable} -c 'import time; time.sleep(3)'\"\n"
    )
    env = {"XDG_RUNTIME_DIR": str(runtime)}
    first = tui(root, "experiments", "exp", "run", env=env, cols=160)
    expect(first.get_by_text("1 at a time")).to_be_visible(timeout=60)
    [path] = runtime.glob("labnotes/*.sock")
    second = tui(root, "experiments", "exp", "run", env=env, cols=160)
    expect(second.get_by_text("0 passed, 0 failed.")).to_be_visible(timeout=60)
    expect(first.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=15)
    assert list(runtime.glob("labnotes/*.sock")) == [path]

    # Attached TUIs keep the idle daemon alive past its idle window.
    time.sleep(5.5)
    assert path.exists()
    tui.quit(first)
    tui.quit(second)
    wait_for(lambda: not path.exists())
    assert not path.exists()
