import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import psutil
import pytest
from curtaincall import expect

SCRIPT = """
import sys
import time
from pathlib import Path

m = sys.argv[sys.argv.index("--m") + 1]
with Path("launches.txt").open("a") as log:
    log.write(m + "\\n")
if m == "a" and Path("fail-once").exists():
    Path("fail-once").unlink()
    sys.exit(1)
while not Path(f"release-{m}").exists():
    time.sleep(0.05)
Path(f"done-{m}").touch()
"""

HOOK = """
import sys
from pathlib import Path

with Path("hooks.txt").open("a") as log:
    log.write(sys.argv[1] + "\\n")
"""


@pytest.fixture(autouse=True)
def cleanup_daemons(tmp_path: Path) -> Iterator[None]:
    yield
    config = str(tmp_path / ".labnotes.toml")
    owners = [
        process
        for process in psutil.process_iter(["cmdline"])
        if "daemon" in (process.info["cmdline"] or [])
        and config in (process.info["cmdline"] or [])
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


def project(root: Path) -> Path:
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


def wait_for(check: Callable[[], bool], timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while not check():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.05)


def hold(check: Callable[[], bool], seconds: float = 3) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        assert check()
        time.sleep(0.05)


def open_run(terminal, root: Path):
    command = Path(sys.executable).parent / "labnotes"
    return terminal(
        f"{command} -c {root / '.labnotes.toml'} experiments exp run",
        rows=30,
        cols=160,
    )


def test_restart_while_the_invocation_is_live_shares_its_setup_and_teardown(
    terminal, tmp_path: Path
) -> None:
    root = project(tmp_path)
    hooks = root / "hooks.txt"
    term = open_run(terminal, root)
    expect(term.get_by_text("✗ exited 1")).to_be_visible(timeout=60)
    assert lines(hooks) == ["setup"]

    term.write("r")
    wait_for(lambda: lines(root / "launches.txt").count("a") == 2)
    assert lines(hooks) == ["setup"]

    (root / "release-b").touch()
    wait_for((root / "done-b").exists)
    hold(lambda: lines(hooks) == ["setup"])
    expect(term.get_by_text("teardown ✓")).not_to_be_visible()

    (root / "release-a").touch()
    expect(term.get_by_text("2 passed, 0 failed. 1 retried.")).to_be_visible(timeout=30)
    expect(term.get_by_text("teardown ✓")).to_be_visible(timeout=30)
    assert lines(hooks) == ["setup", "teardown"]
    term.key_ctrl_c()
    term.wait()


def test_restart_after_teardown_brings_the_invocation_back_up(
    terminal, tmp_path: Path
) -> None:
    root = project(tmp_path)
    hooks = root / "hooks.txt"
    (root / "release-b").touch()
    term = open_run(terminal, root)
    expect(term.get_by_text("1 passed, 1 failed.")).to_be_visible(timeout=60)
    expect(term.get_by_text("teardown ✓")).to_be_visible(timeout=30)
    assert lines(hooks) == ["setup", "teardown"]
    term.write("[")
    expect(term.get_by_text("params")).to_be_visible()

    term.write("r")
    wait_for(lambda: lines(root / "launches.txt").count("a") == 2)
    assert lines(hooks) == ["setup", "teardown", "setup"]
    expect(term.get_by_text("teardown ○")).to_be_visible(timeout=10)

    (root / "release-a").touch()
    expect(term.get_by_text("2 passed, 0 failed. 1 retried.")).to_be_visible(timeout=30)
    expect(term.get_by_text("teardown ✓")).to_be_visible(timeout=30)
    assert lines(hooks) == ["setup", "teardown", "setup", "teardown"]
    term.key_ctrl_c()
    term.wait()
