import json
import time
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_uvx_run_tui_switches_to_configured_view(tmp_path: Path, tui: Tui) -> None:
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
    term = tui(root, "experiments", "alpha", "run", cols=120)
    expect(term.get_by_text("2 progress")).to_be_visible(timeout=60)
    term.write("2")
    expect(term.get_by_text("run view: alpha")).to_be_visible()
    term.write("1")
    expect(term.get_by_text("run view: alpha")).not_to_be_visible()
    tui.stop(term)
    for _ in range(100):
        paths = list(root.glob("alpha/runs/*/run.json"))
        if paths and all(json.loads(path.read_text()).get("ended") for path in paths):
            break
        time.sleep(0.05)
    assert paths
    assert any(json.loads(path.read_text())["ended_by"] == "stop" for path in paths)
