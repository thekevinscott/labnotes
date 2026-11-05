import os
from pathlib import Path

import pytest

from labnotes.cli import main


def test_reports_an_unwritable_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    request: pytest.FixtureRequest,
) -> None:
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    tmp_path.chmod(0o555)
    request.addfinalizer(lambda: tmp_path.chmod(0o755))
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exit_info:
        main(["init"])

    assert exit_info.value.code == 1
    err = capsys.readouterr().err
    assert str(tmp_path / ".labnotes.toml") in err
    assert "Permission denied" in err
    assert "Traceback" not in err
