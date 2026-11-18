import json
import sys
import time
from pathlib import Path

from curtaincall import expect

from conftest import Tui

VIEW = (
    "from textual.binding import Binding\n"
    "from textual.widgets import Static\n"
    "from labnotes.view import Restart, Selected, Stop\n"
    "class Control(Static, can_focus=True):\n"
    "    BINDINGS = [Binding('z', 'stop'), Binding('a', 'restart')]\n"
    "    run = None\n"
    "    def on_labnotes_selected(self, message: Selected):\n"
    "        self.run = message.run\n"
    "        self.update(f'selected run {message.run}')\n"
    "    def action_stop(self):\n"
    "        self.post_message(Stop(self.run))\n"
    "    def action_restart(self):\n"
    "        self.post_message(Restart(self.run))\n"
)


def project(root: Path, command: str) -> None:
    (root / "alpha").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "control.py").write_text(VIEW)
    (root / "alpha/experiment.toml").write_text(
        f'command = "{command}"\ncontinues = false\nretries = 0\n'
        '[views]\ncontrol = "control.py:Control"\n'
    )


def run_ids(root: Path) -> list[str]:
    return [path.parent.name for path in root.glob("alpha/runs/*/run.json")]


def test_uvx_a_view_sees_the_opened_run_and_stops_it(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    project(root, "python -c 'import time; time.sleep(60)'")

    term = tui(root, "experiments", "alpha", "run", cols=120)
    expect(term.get_by_text("2 control")).to_be_visible(timeout=60)
    for _ in range(200):
        if run_ids(root):
            break
        time.sleep(0.05)
    [run] = run_ids(root)
    term.write("2")
    expect(term.get_by_text(f"selected run {run}")).to_be_visible()
    term.write("z")
    path = root / "alpha/runs" / run / "run.json"
    for _ in range(200):
        if json.loads(path.read_text()).get("ended"):
            break
        time.sleep(0.05)
    assert json.loads(path.read_text())["ended_by"] == "stop"
    tui.quit(term)


def test_uvx_a_view_restarts_the_opened_failed_run(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    project(root, f"{sys.executable} script.py")
    (root / "script.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        "with Path('launches.txt').open('a') as log: log.write('go\\n')\n"
        "if Path('fail-once').exists():\n"
        "    Path('fail-once').unlink()\n    sys.exit(1)\n"
    )
    (root / "fail-once").write_text("")

    term = tui(root, "experiments", "alpha", "run", cols=120)
    expect(term.get_by_text("0 passed, 1 failed.")).to_be_visible(timeout=120)
    [run] = run_ids(root)
    term.write("2")
    expect(term.get_by_text(f"selected run {run}")).to_be_visible()
    term.write("a")
    term.write("1")
    expect(term.get_by_text("1 passed, 0 failed. 1 retried.")).to_be_visible(timeout=60)
    assert (root / "launches.txt").read_text().splitlines() == ["go", "go"]
    tui.quit(term)
