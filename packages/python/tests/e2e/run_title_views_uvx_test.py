from pathlib import Path

import pytest
from curtaincall import expect

from conftest import Tui


@pytest.mark.parametrize(
    ("line", "title"), [('name = "Study"\n', "Study"), ("", "alpha")]
)
def test_uvx_run_header_shows_the_experiment_name_with_views(
    tmp_path: Path, tui: Tui, line: str, title: str
) -> None:
    root = tmp_path / "project"
    (root / "alpha").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "alpha/experiment.toml").write_text(
        f'{line}command = "python -c pass"\n'
        'continues = false\n[views]\nzfiles = "files.py:Files"\n'
    )
    (root / "files.py").write_text(
        "from textual.widgets import Static\nclass Files(Static):\n    pass\n"
    )
    term = tui(root, "experiments", "alpha", "run", cols=120)
    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=60)
    header = term._get_screen_text().splitlines()[0]
    assert f"{title} — " in header
    assert "zfiles" not in header
    tui.quit(term)
