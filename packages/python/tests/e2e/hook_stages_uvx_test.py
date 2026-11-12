import json
import re
import sys
from pathlib import Path

import psutil
from curtaincall import expect

from conftest import Tui


def project(tmp_path: Path, setup: str) -> Path:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "setup.py").write_text(setup)
    (root / "exp/experiment.toml").write_text(
        f"continues = false\nrepeats = 2\ncommand = \"{sys.executable} -c 'print(1)'\"\n"
        f'setup = "{sys.executable} setup.py"\n'
        f'teardown = "{sys.executable} -c \'print(\\"down\\")\'"\n'
    )
    return root


def test_uvx_run_keeps_setup_and_teardown_logs_with_the_experiment(
    tmp_path: Path, tui: Tui
) -> None:
    root = project(
        tmp_path, "import sys\nprint('pod up')\nprint('warming', file=sys.stderr)\n"
    )

    term = tui(root, "experiments", "exp", "run")

    expect(term.get_by_text("2 passed, 0 failed.")).to_be_visible(timeout=120)
    term.write("[")
    term.write("[")
    expect(term.get_by_text("pod up")).to_be_visible()
    tui.quit(term)
    logs = root / "exp/.labnotes/logs"
    [setup] = (logs / "setup").iterdir()
    [teardown] = (logs / "teardown").iterdir()
    assert setup.name == teardown.name
    assert (setup / "stdout.log").read_text() == "pod up\n"
    assert (setup / "stderr.log").read_text() == "warming\n"
    assert (teardown / "stdout.log").read_text() == "down\n"
    metadata = json.loads((setup / "metadata.json").read_text())
    runs = sorted(path.name for path in (root / "exp/runs").iterdir())
    assert (metadata["exit_code"], sorted(metadata["runs"])) == (0, runs)


def test_uvx_run_tui_shows_setup_logs_then_the_runs(tmp_path: Path, tui: Tui) -> None:
    root = project(
        tmp_path, "import time\nprint('pod up', flush=True)\ntime.sleep(4)\n"
    )

    term = tui(root, "experiments", "exp", "run")

    expect(term.get_by_text("pod up")).to_be_visible(timeout=60)
    expect(term.get_by_text("setup")).to_be_visible()
    expect(term.get_by_text("2 passed, 0 failed")).to_be_visible(timeout=30)
    term.write("[")
    term.write("[")
    expect(term.get_by_text("pod up")).to_be_visible()
    tui.quit(term)


def test_uvx_ctrl_c_during_setup_stops_the_invocation(tmp_path: Path, tui: Tui) -> None:
    root = project(
        tmp_path, "import time\nprint('pod up', flush=True)\ntime.sleep(4)\n"
    )
    config = str(root / ".labnotes.toml")

    term = tui(root, "experiments", "exp", "run")
    expect(term.get_by_text("pod up")).to_be_visible(timeout=60)
    term.key_ctrl_c()
    expect(term.get_by_text("Setting up. Stop (s)")).to_be_visible()
    term.write("s")
    assert tui.exited(term) == 0, term.to_snapshot()

    daemons = [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (process.info["cmdline"] or [])
        and "daemon" in (process.info["cmdline"] or [])
    ]
    assert daemons
    _, alive = psutil.wait_procs(daemons, timeout=30)
    assert not alive
    assert not list(root.glob("exp/runs/*/run.json"))
    [teardown] = (root / "exp/.labnotes/logs/teardown").iterdir()
    assert (teardown / "stdout.log").read_text() == "down\n"


def test_uvx_run_tui_switches_stage_by_clicking_its_tab(
    tmp_path: Path, tui: Tui
) -> None:
    root = project(
        tmp_path, "import time\nprint('pod up', flush=True)\ntime.sleep(4)\n"
    )

    term = tui(root, "experiments", "exp", "run")

    expect(term.get_by_text("pod up")).to_be_visible(timeout=60)
    expect(term.get_by_text("2 passed, 0 failed")).to_be_visible(timeout=30)
    expect(term.get_by_text("Next stage")).not_to_be_visible()
    expect(term.get_by_text("Previous stage")).not_to_be_visible()
    term.get_by_text(re.compile(r" setup [✓✗] ")).click()
    expect(term.get_by_text("pod up")).to_be_visible()
    term.write("]")
    expect(term.get_by_text("params")).to_be_visible()
    expect(term.get_by_text("pod up")).not_to_be_visible()
    tui.quit(term)
