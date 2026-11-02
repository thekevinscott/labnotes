import json
import os
from pathlib import Path

from curtaincall import expect

PROGRESS = """\
from rich.text import Text
from textual.widgets import Static

from labnotes.view import Changed


class Progress(Static):
    def on_labnotes_changed(self, message: Changed) -> None:
        runs = message.experiment.runs
        passed = sum(row["status"] == "passed" for row in runs.values())
        self.update(Text(f"{passed} of {len(runs)} passed"))
"""


def test_uvx_labnotes_shows_a_view_from_the_project(
    terminal, tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "views").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "views/progress.py").write_text(PROGRESS)
    (root / "alpha").mkdir()
    (root / "alpha/experiment.toml").write_text(
        'continues = false\ncommand = "go"\n'
        '[views]\nprogress = "views/progress.py:Progress"\n'
    )
    for run, code in (("first", 0), ("second", 1)):
        folder = root / "alpha/runs" / run
        folder.mkdir(parents=True)
        (folder / "run.json").write_text(
            json.dumps({"created": "2026-10-17T00:00:00Z", "exit_code": code})
        )

    term = terminal(
        f"uvx labnotes -c {root / '.labnotes.toml'} experiments alpha",
        rows=30,
        cols=120,
        env={**os.environ, **uvx},
    )
    expect(term.get_by_text("progress")).to_be_visible(timeout=60)

    term.write("2")
    expect(term.get_by_text("1 of 2 passed")).to_be_visible()

    term.key_ctrl_c()
    assert term.wait() == 0
