import sys
import time
from collections.abc import Callable
from pathlib import Path

from curtaincall import expect

from conftest import Tui

SCRIPT = (
    "import sys, time\nfrom pathlib import Path\n"
    "m = sys.argv[sys.argv.index('--m') + 1]\n"
    "with Path('launches.txt').open('a') as log: log.write(m + '\\n')\n"
    "if m == 'a' and Path('fail-once').exists():\n"
    "    Path('fail-once').unlink()\n    sys.exit(1)\n"
    "while not Path(f'release-{m}').exists(): time.sleep(0.05)\n"
    "Path(f'done-{m}').touch()\n"
)
HOOK = (
    "import sys\nfrom pathlib import Path\n"
    "with Path('hooks.txt').open('a') as log: log.write(sys.argv[1] + '\\n')\n"
)


def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(SCRIPT)
    (root / "hook.py").write_text(HOOK)
    (root / "fail-once").write_text("")
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\n'
        f'setup = "{sys.executable} hook.py setup"\n'
        f'teardown = "{sys.executable} hook.py teardown"\n'
        "continues = false\nretries = 0\nconcurrency = 2\n"
        '[params]\nm = ["a", "b"]\n'
    )
    return root


def lines(path: Path) -> list[str]:
    return path.read_text().splitlines() if path.exists() else []


def wait_for(check: Callable[[], bool], timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while not check():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.05)


def hold(check: Callable[[], bool], seconds: float = 3) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        assert check()
        time.sleep(0.05)


def test_uvx_restart_while_live_waits_for_every_run_before_teardown(
    tmp_path: Path, tui: Tui
) -> None:
    root = project(tmp_path)
    hooks = root / "hooks.txt"

    term = tui(root, "experiments", "exp", "run")
    expect(term.get_by_text("✗ exited 1")).to_be_visible(timeout=120)
    term.write("r")
    wait_for(lambda: lines(root / "launches.txt").count("a") == 2)
    assert lines(hooks) == ["setup"]

    (root / "release-b").touch()
    wait_for((root / "done-b").exists)
    hold(lambda: lines(hooks) == ["setup"])
    expect(term.get_by_text("teardown ✓")).not_to_be_visible()

    (root / "release-a").touch()
    expect(term.get_by_text("2 passed, 0 failed. 1 retried.")).to_be_visible(timeout=60)
    expect(term.get_by_text("teardown ✓")).to_be_visible(timeout=30)
    assert lines(hooks) == ["setup", "teardown"]
    tui.quit(term)


def test_uvx_restart_after_teardown_sets_the_invocation_up_again(
    tmp_path: Path, tui: Tui
) -> None:
    root = project(tmp_path)
    hooks = root / "hooks.txt"
    (root / "release-b").touch()

    term = tui(root, "experiments", "exp", "run")
    expect(term.get_by_text("1 passed, 1 failed.")).to_be_visible(timeout=120)
    expect(term.get_by_text("teardown ✓")).to_be_visible(timeout=30)
    term.write("[")
    expect(term.get_by_text("params")).to_be_visible()
    term.write("r")
    wait_for(lambda: lines(root / "launches.txt").count("a") == 2)
    assert lines(hooks) == ["setup", "teardown", "setup"]
    expect(term.get_by_text("teardown ○")).to_be_visible(timeout=10)

    (root / "release-a").touch()
    expect(term.get_by_text("2 passed, 0 failed. 1 retried.")).to_be_visible(timeout=60)
    expect(term.get_by_text("teardown ✓")).to_be_visible(timeout=30)
    assert lines(hooks) == ["setup", "teardown", "setup", "teardown"]
    tui.quit(term)
