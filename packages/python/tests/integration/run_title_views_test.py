import sys
from pathlib import Path

import pytest
from conftest import run_tui_command, write


@pytest.mark.parametrize(
    ("line", "title"), [('name = "Study"\n', "Study"), ("", "exp")]
)
def test_run_header_shows_the_experiment_name_with_views(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], line: str, title: str
) -> None:
    write(tmp_path / ".labnotes.toml", '[experiments]\npath = "{experiment}"\n')
    write(
        tmp_path / "exp" / "experiment.toml",
        f'{line}continues = false\ncommand = "{sys.executable} -c pass"\n'
        '[views]\nzfiles = "files.py:Files"\n',
    )
    write(
        tmp_path / "files.py",
        "from textual.widgets import Static\nclass Files(Static):\n    pass\n",
    )

    assert run_tui_command(tmp_path, ["experiments", "exp", "run"]) == 0
    header = capsys.readouterr().out.splitlines()[0]
    assert f"{title} — " in header
    assert "zfiles" not in header
