import shlex
import time
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import curtaincall
import pytest

from conftest import run_tui_command


def scripted(script: str, stale: bool = False):
    class Scripted(curtaincall.Terminal):
        def __init__(self, command: str, **kwargs) -> None:
            super().__init__("/bin/sh -c " + shlex.quote(script), **kwargs)

        def _get_screen_text(self) -> str:
            text = super()._get_screen_text()
            while stale and self.is_alive:
                time.sleep(0.01)
            return text

    return mock.patch.object(curtaincall, "Terminal", Scripted)


def exits_before_answering(self: curtaincall.Terminal) -> bool:
    while self._child_alive():
        time.sleep(0.01)
    return False


@pytest.fixture
def prints_on_exit() -> Iterator[None]:
    with scripted("sleep 0.5; printf 'printed on exit'; exit 3", stale=True):
        yield


@pytest.fixture
def prints_after_close() -> Iterator[None]:
    with scripted(
        "trap 'printf \"printed after close\\n\"; exit 0' INT; "
        "printf '1 passed, 0 failed.\\n'; while :; do sleep 0.05; done"
    ):
        yield


@pytest.fixture
def late_exit_check() -> Iterator[None]:
    with mock.patch.object(
        curtaincall.Terminal, "is_alive", property(exits_before_answering)
    ):
        yield


@pytest.mark.usefixtures("prints_on_exit")
def test_reads_the_screen_after_the_process_exits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_tui_command(tmp_path, []) == 3
    assert "printed on exit" in capsys.readouterr().err


@pytest.mark.usefixtures("prints_after_close")
def test_keeps_output_printed_after_the_tui_closes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_tui_command(tmp_path, []) == 0
    out = capsys.readouterr().out
    assert "printed after close" in out
    assert out.endswith("1 passed, 0 failed.\n")


@pytest.mark.usefixtures("late_exit_check")
def test_reports_what_the_cli_printed_before_it_exited(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".labnotes.toml").write_text("")

    code = run_tui_command(
        tmp_path, ["experiments", "exp", "run", "--run-id", "x", "--", "y"]
    )

    assert code != 0
    assert "--run-id uses the run's recorded params" in capsys.readouterr().err
