import re
import shlex
import sys
from collections.abc import Iterator
from pathlib import Path

from curtaincall import Terminal, expect
import psutil
import pytest

PYTHON = shlex.quote(sys.executable)
QUICK = f"{PYTHON} -c 'print(1)'"
BREADCRUMBS = re.compile(r"setup .*›.* runs .*›.* teardown")


@pytest.fixture(autouse=True)
def cleanup_daemons(tmp_path: Path) -> Iterator[None]:
    yield
    config = str(tmp_path / ".labnotes.toml")
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


def script(tmp_path: Path, name: str, body: str) -> str:
    path = tmp_path / f"{name}.py"
    path.write_text(f"import sys, time\n{body}")
    return f"{PYTHON} {path}"


def run_tui(terminal, tmp_path: Path, hooks: str, command: str = QUICK) -> Terminal:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp" / "experiment.toml").write_text(
        f"continues = false\ncommand = '''{command}'''\nrepeats = 2\n{hooks}"
    )
    labnotes = Path(sys.executable).parent / "labnotes"
    return terminal(
        f"{labnotes} -c {tmp_path / '.labnotes.toml'} experiments exp run",
        rows=30,
        cols=120,
    )


def quit_tui(term: Terminal, running: bool = False) -> None:
    term.key_ctrl_c()
    if running:
        expect(term.get_by_text("leave running")).to_be_visible()
        term.write("l")
    term.wait()


def test_setup_shows_its_logs_then_advances_to_the_runs(
    terminal, tmp_path: Path
) -> None:
    setup = script(
        tmp_path,
        "setup",
        "for i in range(4):\n"
        "    print('setup out', i, flush=True)\n"
        "    print('setup err', i, file=sys.stderr, flush=True)\n"
        "    time.sleep(0.5)\n",
    )
    teardown = script(tmp_path, "teardown", "time.sleep(30)\n")
    hooks = f"setup = '''{setup}'''\nteardown = '''{teardown}'''\n"
    term = run_tui(
        terminal, tmp_path, hooks, f"{PYTHON} -c 'import time; time.sleep(20)'"
    )

    expect(term.get_by_text(BREADCRUMBS)).to_be_visible(timeout=15)
    expect(term.get_by_text("setup out 1")).to_be_visible()
    expect(term.get_by_text("setup err 1")).to_be_visible()
    expect(term.get_by_text("params")).not_to_be_visible()

    expect(term.get_by_text("params")).to_be_visible(timeout=15)
    expect(term.get_by_text("setup out 1")).not_to_be_visible()

    term.write("[")
    expect(term.get_by_text("setup out 3")).to_be_visible()
    expect(term.get_by_text(re.compile("setup ✓"))).to_be_visible()

    quit_tui(term, running=True)


def test_teardown_shows_its_logs_once_the_runs_finish(terminal, tmp_path: Path) -> None:
    teardown = script(
        tmp_path,
        "teardown",
        "print('teardown out', flush=True)\ntime.sleep(30)\n",
    )
    term = run_tui(terminal, tmp_path, f"teardown = '''{teardown}'''\n")

    expect(term.get_by_text("teardown out")).to_be_visible(timeout=15)
    expect(term.get_by_text("params")).not_to_be_visible()
    expect(term.get_by_text(re.compile(r"runs ✓.*›.* teardown"))).to_be_visible()

    quit_tui(term, running=True)


def test_moving_between_stages_by_hand_stops_auto_advance(
    terminal, tmp_path: Path
) -> None:
    setup = script(
        tmp_path, "setup", "print('setup begun', flush=True)\ntime.sleep(3)\n"
    )
    term = run_tui(terminal, tmp_path, f"setup = '''{setup}'''\n")
    expect(term.get_by_text("setup begun")).to_be_visible(timeout=15)

    term.write("]")
    expect(term.get_by_text("params")).to_be_visible()
    term.write("[")
    expect(term.get_by_text("setup begun")).to_be_visible()

    expect(term.get_by_text(re.compile("setup ✓"))).to_be_visible(timeout=15)
    expect(term.get_by_text(re.compile("runs ✓"))).to_be_visible(timeout=15)
    expect(term.get_by_text("setup begun")).to_be_visible()
    expect(term.get_by_text("params")).not_to_be_visible()

    quit_tui(term)


def daemons(tmp_path: Path) -> list[psutil.Process]:
    config = str(tmp_path / ".labnotes.toml")
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (process.info["cmdline"] or [])
        and "daemon" in (process.info["cmdline"] or [])
    ]


def setting_up(terminal, tmp_path: Path) -> Terminal:
    setup = script(
        tmp_path, "setup", "print('setup begun', flush=True)\ntime.sleep(3)\n"
    )
    teardown = script(
        tmp_path, "teardown", f"open({str(tmp_path / 'down')!r}, 'w').close()\n"
    )
    hooks = f"setup = '''{setup}'''\nteardown = '''{teardown}'''\n"
    term = run_tui(terminal, tmp_path, hooks)
    expect(term.get_by_text("setup begun")).to_be_visible(timeout=15)
    term.key_ctrl_c()
    expect(term.get_by_text("Setting up. Stop (s)")).to_be_visible()
    return term


def test_ctrl_c_during_setup_can_stop_the_invocation(terminal, tmp_path: Path) -> None:
    term = setting_up(terminal, tmp_path)
    assert daemons(tmp_path)

    term.write("s")
    term.wait(timeout=10)

    _, alive = psutil.wait_procs(daemons(tmp_path), timeout=30)
    assert not alive
    assert (tmp_path / "down").exists()
    assert not list(tmp_path.glob("exp/runs/*/run.json"))


def test_leaving_during_setup_names_the_stop_command(terminal, tmp_path: Path) -> None:
    term = setting_up(terminal, tmp_path)

    term.write("l")
    term.wait(timeout=10)

    expect(
        term.get_by_text(
            "exp is still running. Stop it with: labnotes experiments exp stop"
        )
    ).to_be_visible()
    assert daemons(tmp_path)


def test_a_failed_setup_shows_as_failed_with_its_logs(terminal, tmp_path: Path) -> None:
    setup = script(
        tmp_path, "setup", "print('setup broke', file=sys.stderr)\nsys.exit(3)\n"
    )
    term = run_tui(terminal, tmp_path, f"setup = '''{setup}'''\n")

    expect(term.get_by_text(re.compile("setup ✗"))).to_be_visible(timeout=15)
    expect(term.get_by_text("setup broke")).to_be_visible()

    quit_tui(term)


def test_no_hooks_shows_no_stages(terminal, tmp_path: Path) -> None:
    term = run_tui(terminal, tmp_path, "")

    expect(term.get_by_text("2 passed, 0 failed")).to_be_visible(timeout=15)
    expect(term.get_by_text("›")).not_to_be_visible()

    quit_tui(term)
