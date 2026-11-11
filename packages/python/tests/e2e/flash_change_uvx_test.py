import sys
import time
from collections.abc import Callable
from pathlib import Path

from curtaincall import Terminal, expect

from conftest import Tui


def label_against_header(term: Terminal, text: str) -> tuple[str, str]:
    """Return the label's background and the header's just left of its padding."""
    cell = term.get_by_text(text).cells[0]
    return (
        term._get_char_at(cell.row, cell.col).bg,
        term._get_char_at(cell.row, cell.col - 2).bg,
    )


def wait_for(check: Callable[[], bool], timeout: float, message: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.05)
    raise AssertionError(message)


def test_concurrency_label_flashes_when_changed(tmp_path: Path, tui: Tui) -> None:
    (tmp_path / "exp").mkdir()
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp/experiment.toml").write_text(
        "continues = false\nrepeats = 3\n"
        f"command = \"{sys.executable} -c 'import time; time.sleep(30)'\"\n"
    )
    term = tui(tmp_path, "experiments", "exp", "run", cols=120)

    expect(term.get_by_text("1 at a time")).to_be_visible(timeout=30)
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        label, header = label_against_header(term, "1 at a time")
        assert label == header, term.to_snapshot()
        time.sleep(0.05)

    term.write("+")
    expect(term.get_by_text("2 at a time")).to_be_visible()
    wait_for(
        lambda: len(set(label_against_header(term, "2 at a time"))) == 2,
        1.0,
        "concurrency label never flashed",
    )
    wait_for(
        lambda: len(set(label_against_header(term, "2 at a time"))) == 1,
        3.0,
        "concurrency label never returned to the header background",
    )
    tui.stop(term)
