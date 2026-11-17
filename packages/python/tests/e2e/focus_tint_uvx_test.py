import sys
import time
from pathlib import Path

from curtaincall import expect

from conftest import Tui

SCRIPT = "import time\nprint('para one\\npara two', flush=True)\ntime.sleep(60)\n"
SHIFT_TAB = "\x1b[Z"


def test_uvx_run_drops_the_focus_tint_from_every_output_row(
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
    focused = term._get_char_at(cell.row, cell.col).bg
    term.write(SHIFT_TAB)
    expect(term.get_by_text("para one")).to_be_visible()
    deadline = time.monotonic() + 10
    while term._get_char_at(cell.row + 4, cell.col).bg == focused:
        assert time.monotonic() < deadline, term.to_snapshot()
        time.sleep(0.1)
    text = term._get_char_at(cell.row, cell.col).bg
    blank = term._get_char_at(cell.row + 4, cell.col).bg
    assert text == blank, term.to_snapshot()
    tui.stop(term)
