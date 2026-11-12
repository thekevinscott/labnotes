import json
import os
import shutil
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import psutil
import pytest
from curtaincall import expect

from conftest import Tui


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        yield Path(folder)


def project(root: Path, release: Path) -> Path:
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "hold.py").write_text(
        "import time\nfrom pathlib import Path\n"
        "print('holding', flush=True)\n"
        f"while not Path({str(release)!r}).exists():\n    time.sleep(0.05)\n"
    )
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} hold.py"\n'
    )
    return root


def trash_run_state() -> None:
    shutil.rmtree(Path(os.environ["XDG_STATE_HOME"]) / "labnotes" / "run-state")


def record(root: Path) -> dict[str, object]:
    [path] = root.glob("exp/runs/*/run.json")
    return json.loads(path.read_text())


def test_tui_keeps_its_view_after_run_state_is_deleted(
    tmp_path: Path, tui: Tui, runtime: Path
) -> None:
    release = tmp_path / "release"
    root = project(tmp_path / "project", release)
    term = tui(root, "experiments", "exp", "run", env={"XDG_RUNTIME_DIR": str(runtime)})
    expect(term.get_by_text("holding")).to_be_visible(timeout=120)
    trash_run_state()
    release.touch()
    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=30)
    tui.quit(term)


def test_tui_still_controls_its_daemon_after_run_state_is_deleted(
    tmp_path: Path, tui: Tui, runtime: Path
) -> None:
    root = project(tmp_path / "project", tmp_path / "never")
    term = tui(root, "experiments", "exp", "run", env={"XDG_RUNTIME_DIR": str(runtime)})
    expect(term.get_by_text("holding")).to_be_visible(timeout=120)
    trash_run_state()
    tui.stop(term)
    assert not term.get_by_text("No daemon is running").is_visible()
    for _ in range(200):
        if record(root).get("ended") is not None:
            break
        time.sleep(0.05)
    assert record(root)["ended_by"] == "stop"


def test_tui_shows_a_lost_daemon_at_once(
    tmp_path: Path, tui: Tui, runtime: Path
) -> None:
    root = project(tmp_path / "project", tmp_path / "never")
    term = tui(root, "experiments", "exp", "run", env={"XDG_RUNTIME_DIR": str(runtime)})
    expect(term.get_by_text("holding")).to_be_visible(timeout=120)
    config = str(root / ".labnotes.toml")
    for process in psutil.process_iter(["cmdline"]):
        cmdline = process.info["cmdline"] or []
        if config in cmdline and "daemon" in cmdline:
            process.kill()
    expect(term.get_by_text("Lost the daemon for exp.")).to_be_visible(timeout=15)
    term.write("q")
    assert tui.exited(term) != 0
