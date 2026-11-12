import shlex
import time
from pathlib import Path

import curtaincall
import pytest

from conftest import run_tui_command


def substitute(monkeypatch: pytest.MonkeyPatch, script: str, stale: bool = False):
    class Scripted(curtaincall.Terminal):
        def __init__(self, command: str, **kwargs) -> None:
            super().__init__("/bin/sh -c " + shlex.quote(script), **kwargs)

        def _get_screen_text(self) -> str:
            text = super()._get_screen_text()
            while stale and self.is_alive:
                time.sleep(0.01)
            return text

    monkeypatch.setattr(curtaincall, "Terminal", Scripted)


def test_reads_the_screen_after_the_process_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    substitute(monkeypatch, "sleep 0.5; printf 'printed on exit'; exit 3", stale=True)

    assert run_tui_command(tmp_path, []) == 3
    assert "printed on exit" in capsys.readouterr().err


def test_keeps_output_printed_after_the_tui_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    substitute(
        monkeypatch,
        "trap 'printf \"printed after close\\n\"; exit 0' INT; "
        "printf '1 passed, 0 failed.\\n'; while :; do sleep 0.05; done",
    )

    assert run_tui_command(tmp_path, []) == 0
    out = capsys.readouterr().out
    assert "printed after close" in out
    assert out.endswith("1 passed, 0 failed.\n")
