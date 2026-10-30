import os
import subprocess
from pathlib import Path

import pytest

PACKAGE = Path(__file__).parents[2]


@pytest.fixture
def uvx(tmp_path: Path) -> dict[str, str]:
    # Install this checkout as the uv tool so uvx runs it offline.
    env = {"UV_NO_CONFIG": "1", "UV_TOOL_DIR": str(tmp_path / "tools")}
    constraints = tmp_path / "constraints.txt"
    uv = ["uv", "--directory", str(PACKAGE)]
    subprocess.run(
        [*uv, "export", "-q", "--frozen", "--no-dev", "--no-emit-project"]
        + ["-o", str(constraints)],
        check=True,
    )
    # Rebuild labnotes so uncommitted source changes are tested, too.
    subprocess.run(
        [*uv, "tool", "install", "-q", "--refresh-package", "labnotes"]
        + ["-c", str(constraints), "."],
        check=True,
        env={**os.environ, **env, "UV_TOOL_BIN_DIR": str(tmp_path / "bin")},
    )
    return {**env, "UV_OFFLINE": "1"}
