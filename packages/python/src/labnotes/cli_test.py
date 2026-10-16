import json
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path
from unittest import mock

import pytest

from labnotes.cli import main

ROWS = [{"name": "a", "study": "s1", "runs": 3}]


@pytest.fixture
def list_experiments() -> Iterator[mock.AsyncMock]:
    with mock.patch(
        "labnotes.cli.list_experiments", new_callable=mock.AsyncMock, return_value=ROWS
    ) as patched:
        yield patched


def test_version_prints_installed_version(
    capsys: pytest.CaptureFixture[str], list_experiments: mock.AsyncMock
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == version("labnotes")
    list_experiments.assert_not_awaited()


def test_prints_experiments_as_json(
    capsys: pytest.CaptureFixture[str], list_experiments: mock.AsyncMock
) -> None:
    main(["--experiments-folder", "exp", "--data-folder", "data"])

    list_experiments.assert_awaited_once_with(Path("exp"), Path("data"))
    assert json.loads(capsys.readouterr().out) == ROWS


def test_requires_both_folders(list_experiments: mock.AsyncMock) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--experiments-folder", "exp"])
    assert exit_info.value.code == 2
    list_experiments.assert_not_awaited()
