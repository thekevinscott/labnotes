import re
import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_uvx_args_override_a_flag_in_the_command(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text("import sys\nprint(*sys.argv[1:])\n")
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} script.py --memory 8g --output {{run_dir}}"\n'
    )

    term = tui(
        root, "experiments", "exp", "run", "--", "--memory", "24g", "--auth", "api"
    )

    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=120)
    shown = re.compile(r"--memory 24g --output \S+ --auth api")
    expect(term.get_by_text(shown)).to_be_visible()
    tui.quit(term)
