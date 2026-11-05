import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

from curtaincall import expect
import psutil
import pytest


@pytest.fixture(autouse=True)
def cleanup_daemon(tmp_path: Path) -> Iterator[None]:
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
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = project(
        tmp_path, "import sys\nprint('pod up')\nprint('warming', file=sys.stderr)\n"
    )

    result = subprocess.run(
        ["uvx", "labnotes", "-c", str(root / ".labnotes.toml"), "experiments", "exp"]
        + ["run"],
        cwd=root,
        env={**os.environ, **uvx},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
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


def test_uvx_run_tui_shows_setup_logs_then_the_runs(
    terminal, tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = project(
        tmp_path, "import time\nprint('pod up', flush=True)\ntime.sleep(4)\n"
    )

    term = terminal(
        f"uvx labnotes -c {root / '.labnotes.toml'} experiments exp run",
        rows=30,
        cols=120,
        env={**os.environ, **uvx},
    )

    expect(term.get_by_text("pod up")).to_be_visible(timeout=60)
    expect(term.get_by_text("setup")).to_be_visible()
    expect(term.get_by_text("2 passed, 0 failed")).to_be_visible(timeout=30)
    term.write("[")
    term.write("[")
    expect(term.get_by_text("pod up")).to_be_visible()
    term.key_ctrl_c()
    term.wait()
