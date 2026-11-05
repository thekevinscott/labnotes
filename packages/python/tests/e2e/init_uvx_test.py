import os
import subprocess
from pathlib import Path

import pytest


def test_uvx_init_reports_an_unwritable_folder(
    tmp_path: Path, uvx: dict[str, str], request: pytest.FixtureRequest
) -> None:
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    root = tmp_path / "project"
    root.mkdir()
    root.chmod(0o555)
    request.addfinalizer(lambda: root.chmod(0o755))

    result = subprocess.run(
        ["uvx", "labnotes", "init"],
        cwd=root,
        env={**os.environ, **uvx},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )

    assert result.returncode == 1, result.stdout
    assert "Traceback" not in result.stdout
    assert ".labnotes.toml" in result.stdout
    assert "Permission denied" in result.stdout
