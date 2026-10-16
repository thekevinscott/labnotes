import json
from importlib.metadata import version
from pathlib import Path
from unittest import mock

import pytest

from labnotes import cli


def test_version_prints_installed_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == version("labnotes")


def test_prints_experiments_as_json(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [{"name": "a", "study": "s1", "runs": 3}]
    with mock.patch.object(
        cli, "list_experiments", mock.AsyncMock(return_value=rows)
    ) as listed:
        cli.main(["--experiments-folder", "exp", "--data-folder", "data"])

    listed.assert_awaited_once_with(Path("exp"), Path("data"))
    assert json.loads(capsys.readouterr().out) == rows


def test_requires_both_folders() -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--experiments-folder", "exp"])
    assert exit_info.value.code == 2
