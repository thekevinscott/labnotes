import json
import os
import time
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


def test_uvx_run_tui_switches_to_configured_view(
    terminal, tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "alpha").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "alpha/experiment.toml").write_text(
        "command = \"python -c 'import time; time.sleep(20)'\"\n"
        'continues = false\n[views]\nprogress = "progress.py:Progress"\n'
    )
    (root / "progress.py").write_text(
        "from textual.widgets import Static\n"
        "from labnotes.view import Changed\n"
        "class Progress(Static):\n"
        "    def on_labnotes_changed(self, message: Changed):\n"
        "        self.update(f'run view: {message.experiment.name}')\n"
    )
    term = terminal(
        f"uvx labnotes -c {root / '.labnotes.toml'} experiments alpha run",
        rows=30,
        cols=120,
        env={**os.environ, **uvx},
    )
    expect(term.get_by_text("2 progress")).to_be_visible(timeout=60)
    term.write("2")
    expect(term.get_by_text("run view: alpha")).to_be_visible()
    term.write("1")
    expect(term.get_by_text("run view: alpha")).not_to_be_visible()
    term.key_ctrl_c()
    term.write("s")
    term.wait()
    for _ in range(100):
        paths = list(root.glob("alpha/runs/*/run.json"))
        if paths and all(json.loads(path.read_text()).get("ended") for path in paths):
            break
        time.sleep(0.05)
    assert paths
    assert any(json.loads(path.read_text())["ended_by"] == "stop" for path in paths)
