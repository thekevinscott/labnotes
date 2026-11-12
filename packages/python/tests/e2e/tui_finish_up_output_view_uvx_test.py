import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_installed_tui_keeps_finish_up_line_after_leaving_output_view(
    tmp_path: Path, tui: Tui
) -> None:
    (tmp_path / "exp").mkdir()
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp/experiment.toml").write_text(
        "continues = false\nrepeats = 2\n"
        f"command = \"{sys.executable} -c 'import time; time.sleep(8)'\"\n"
    )
    term = tui(tmp_path, "experiments", "exp", "run", cols=120)

    expect(term.get_by_text("1 at a time")).to_be_visible(timeout=30)
    term.key_enter()
    expect(term.get_by_text("Back")).to_be_visible()
    term.write("f")
    expect(term.get_by_text("Finishing up")).to_be_visible()
    term.key_escape()
    expect(term.get_by_text("Back")).not_to_be_visible()
    expect(
        term.get_by_text(
            "Finishing up. Queued runs won't start; running cells will finish."
        )
    ).to_be_visible()
    expect(term.get_by_text("1 passed, 0 failed")).to_be_visible(timeout=20)
    tui.check(term)
    tui.quit(term)
