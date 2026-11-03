import json
import sys
from pathlib import Path

from curtaincall import Terminal, expect

PROGRESS = """\
from textual.widgets import Static

from labnotes.view import Changed


class Progress(Static):
    def on_labnotes_changed(self, message: Changed) -> None:
        experiment = message.experiment
        if experiment is None:
            self.update("progress: gone")
            return
        self.update(f"progress: {len(experiment.runs)} runs in {experiment.name}")
"""

STAGES = """\
from textual.binding import Binding
from textual.widgets import Static


class Stages(Static, can_focus=True):
    BINDINGS = [Binding("escape", "up", "Up")]

    def on_mount(self) -> None:
        self.depth = 2
        self.update("stage 2")

    def check_action(self, action, parameters):
        return action != "up" or self.depth > 0

    def action_up(self) -> None:
        self.depth -= 1
        self.update(f"stage {self.depth}")
        self.refresh_bindings()
"""

BOOM = """\
from textual.widget import Widget


class Boom(Widget):
    def compose(self):
        raise RuntimeError("view broke while mounting")
        yield
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def project(root: Path, views: dict[str, str]) -> Path:
    write(root / ".labnotes.toml", "")
    table = "".join(f"{name} = {json.dumps(spec)}\n" for name, spec in views.items())
    write(
        root / "alpha/experiment.toml",
        f'continues = false\ncommand = "go"\n[views]\n{table}',
    )
    for run in ("20261017-000000/first", "20261017-000000/second"):
        write(
            root / f"alpha/runs/{run}/run.json",
            json.dumps({"created": "2026-10-17T00:00:00Z", "exit_code": 0}),
        )
    write(root / "views/progress.py", PROGRESS)
    write(root / "views/stages.py", STAGES)
    write(root / "views/boom.py", BOOM)
    return root


def labnotes(terminal, root: Path, argv: str) -> Terminal:
    command = Path(sys.executable).parent / "labnotes"
    return terminal(
        f"{command} -c {root / '.labnotes.toml'} experiments {argv}",
        rows=30,
        cols=120,
    )


def test_switches_between_the_runs_table_and_a_view_that_updates_live(
    terminal, tmp_path: Path
) -> None:
    root = project(tmp_path, {"progress": "views/progress.py:Progress"})
    term = labnotes(terminal, root, "alpha")
    expect(term.get_by_text("20261017-000000/first")).to_be_visible()
    expect(term.get_by_text("progress")).to_be_visible()
    expect(term.get_by_text("1 runs")).to_be_visible()

    term.write("2")
    expect(term.get_by_text("progress: 2 runs in alpha")).to_be_visible()
    expect(term.get_by_text("20261017-000000/first")).not_to_be_visible()

    write(
        root / "alpha/runs/20261018-000000/first/run.json",
        json.dumps({"created": "2026-10-18T00:00:00Z", "exit_code": 1}),
    )
    expect(term.get_by_text("progress: 3 runs in alpha")).to_be_visible()

    term.write("1")
    expect(term.get_by_text("20261018-000000/first")).to_be_visible()

    term.write("2")
    expect(term.get_by_text("progress: 3 runs")).to_be_visible()
    term.write("0")
    expect(term.get_by_text("20261017-000000/first")).to_be_visible()

    term.key_ctrl_c()
    term.wait()


def test_shows_no_view_keys_with_only_the_built_in_view(
    terminal, tmp_path: Path
) -> None:
    term = labnotes(terminal, project(tmp_path, {}), "alpha")
    expect(term.get_by_text("20261017-000000/first")).to_be_visible()
    expect(term.get_by_text("Back")).to_be_visible()
    expect(term.get_by_text("1 runs")).not_to_be_visible()

    term.write("0")
    expect(term.get_by_text("20261017-000000/first")).to_be_visible()

    term.key_ctrl_c()
    term.wait()


def test_each_view_keeps_its_state(terminal, tmp_path: Path) -> None:
    root = project(tmp_path, {"progress": "views/progress.py:Progress"})
    write(root / "alpha/runs/20261017-000000/second/stdout.log", "hello from second\n")
    term = labnotes(terminal, root, "alpha")
    expect(term.get_by_text("20261017-000000/first")).to_be_visible()

    term.key_enter()
    expect(term.get_by_text("hello from second")).to_be_visible()

    term.write("2")
    expect(term.get_by_text("progress: 2 runs in alpha")).to_be_visible()
    expect(term.get_by_text("hello from second")).not_to_be_visible()

    term.write("1")
    expect(term.get_by_text("hello from second")).to_be_visible()

    term.key_escape()
    expect(term.get_by_text("20261017-000000/first")).to_be_visible()

    term.key_ctrl_c()
    term.wait()


def test_escape_goes_to_the_view_first(terminal, tmp_path: Path) -> None:
    root = project(tmp_path, {"stages": "views/stages.py:Stages"})
    term = labnotes(terminal, root, "alpha")
    expect(term.get_by_text("20261017-000000/first")).to_be_visible()

    term.write("2")
    expect(term.get_by_text("stage 2")).to_be_visible()
    term.key_escape()
    expect(term.get_by_text("stage 1")).to_be_visible()
    term.key_escape()
    expect(term.get_by_text("stage 0")).to_be_visible()

    term.key_escape()
    expect(term.get_by_text("20261017-000000/first")).to_be_visible()

    term.key_escape()
    expect(term.get_by_text("display_name")).to_be_visible()

    term.key_ctrl_c()
    term.wait()


def test_a_view_that_fails_shows_why_and_the_rest_keep_working(
    terminal, tmp_path: Path
) -> None:
    root = project(
        tmp_path,
        {
            "missing": "views/progress.py:Missing",
            "boom": "views/boom.py:Boom",
            "progress": "views/progress.py:Progress",
        },
    )
    term = labnotes(terminal, root, "alpha")
    expect(term.get_by_text("20261017-000000/first")).to_be_visible()

    term.write("2")
    expect(term.get_by_text("views/progress.py has no Missing")).to_be_visible()

    term.write("3")
    expect(term.get_by_text("view broke while mounting")).to_be_visible()

    term.write("4")
    expect(term.get_by_text("progress: 2 runs in alpha")).to_be_visible()

    term.write("1")
    expect(term.get_by_text("20261017-000000/first")).to_be_visible()

    term.key_ctrl_c()
    assert term.wait() == 0
