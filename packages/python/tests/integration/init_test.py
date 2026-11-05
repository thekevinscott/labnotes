import os
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.cli import main


@pytest.fixture
def unwritable_folder(tmp_path: Path) -> Iterator[Path]:
    tmp_path.chmod(0o555)
    try:
        with mock.patch("pathlib.Path.cwd", return_value=tmp_path):
            yield tmp_path
    finally:
        tmp_path.chmod(0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_reports_an_unwritable_folder(
    unwritable_folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["init"])

    assert exit_info.value.code == 1
    err = capsys.readouterr().err
    assert str(unwritable_folder / ".labnotes.toml") in err
    assert "Permission denied" in err
    assert "Traceback" not in err
