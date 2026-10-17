from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.init import init


@pytest.fixture
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.chdir(tmp_path)
    with mock.patch("labnotes.init.default_config_text", return_value="TEXT\n"):
        yield tmp_path


def run() -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        init.main([], prog_name="init")
    return exit_info.value.code


def test_writes_the_default_config_here(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run() == 0

    assert (folder / ".labnotes.toml").read_text(encoding="utf-8") == "TEXT\n"
    assert capsys.readouterr().out == f"Wrote {folder / '.labnotes.toml'}\n"


def test_refuses_to_overwrite_a_config(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (folder / ".labnotes.toml").write_text("mine\n", encoding="utf-8")

    assert run() == 1

    assert (folder / ".labnotes.toml").read_text(encoding="utf-8") == "mine\n"
    assert "already exists" in capsys.readouterr().err
