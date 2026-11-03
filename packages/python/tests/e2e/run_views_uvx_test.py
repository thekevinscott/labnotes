import os
from pathlib import Path

from curtaincall import expect


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
    expect(term.get_by_text("progress")).to_be_visible(timeout=60)
    term.write("2")
    expect(term.get_by_text("run view: alpha")).to_be_visible()
    term.write("1")
    expect(term.get_by_text("run view: alpha")).not_to_be_visible()
    term.key_ctrl_c()
    term.write("s")
    expect(term.get_by_text("Ctrl-C to quit")).to_be_visible(timeout=15)
    term.key_ctrl_c()
    term.wait()
