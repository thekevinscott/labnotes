import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui

SCRIPT = "import time\nprint('para one\\n\\npara two', flush=True)\ntime.sleep(60)\n"


def test_uvx_run_draws_plain_output_on_the_log_background(
    tmp_path: Path, tui: Tui
) -> None:
    (tmp_path / "exp").mkdir()
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp/script.py").write_text(SCRIPT)
    (tmp_path / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} {tmp_path}/exp/script.py"\n'
    )
    term = tui(tmp_path, "experiments", "exp", "run", rows=24, cols=80)

    expect(term.get_by_text("para two")).to_be_visible(timeout=60)
    cell = term.get_by_text("para one").cells[0]
    text = term._get_char_at(cell.row, cell.col).bg
    padding = term._get_char_at(cell.row, cell.col + 20).bg
    blank = term._get_char_at(cell.row + 1, cell.col).bg
    assert (text, blank) == (padding, padding), term.to_snapshot()
    assert padding != "default", term.to_snapshot()
    tui.stop(term)
