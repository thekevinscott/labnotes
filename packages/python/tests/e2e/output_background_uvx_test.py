import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui

SCRIPT = (
    "import time\n"
    "print('first paragraph line\\n\\nsecond paragraph line', flush=True)\n"
    "time.sleep(60)\n"
)


def test_uvx_run_output_text_sits_on_the_log_background(
    tmp_path: Path, tui: Tui
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/script.py").write_text(SCRIPT)
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} {root}/exp/script.py"\n'
    )

    term = tui(root, "experiments", "exp", "run", rows=24, cols=80)

    for text in ("first paragraph line", "second paragraph line"):
        line = term.get_by_text(text)
        expect(line).to_be_visible(timeout=60)
        cell = line.cells[-1]
        # Compare with the padding just right of the text, which is the log's own fill.
        padding = term._get_char_at(cell.row, cell.col + 1).bg
        assert padding != "default", term.to_snapshot()
        expect(line).to_have_bg_color(padding)
    tui.stop(term)
