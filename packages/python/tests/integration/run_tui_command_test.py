import time
from pathlib import Path

import pytest
from curtaincall import Terminal

from conftest import run_tui_command


def test_reports_what_the_command_printed_before_it_exited(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / ".labnotes.toml").write_text("")

    def exits_before_answering(self: Terminal) -> bool:
        while self._child_alive():
            time.sleep(0.01)
        return False

    monkeypatch.setattr(Terminal, "is_alive", property(exits_before_answering))

    code = run_tui_command(
        tmp_path, ["experiments", "exp", "run", "--run-id", "x", "--", "y"]
    )

    assert code != 0
    assert "--run-id uses the run's recorded params" in capsys.readouterr().err
