import shlex
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

BOTBOX_CONTAINER = """
import os
import subprocess
from pathlib import Path

folder = Path(os.environ["LABNOTES_RUN"])
labels = folder / "botbox-labels.txt"
labels.write_text(os.environ["BOTBOX_LABELS"])
subprocess.run([
    "docker", "run", "--rm", "--label-file", str(labels),
    "--cidfile", str(folder / "container.cid"),
    "python:3.12-slim", "python", "-c",
    "held = b'x' * 200_000_000; print(len(held), flush=True); "
    "import time; time.sleep(3)",
], check=True)
"""

HOOK = """
import os
import sys
from pathlib import Path

Path(sys.argv[1] + "-labels.txt").write_text(os.environ["BOTBOX_LABELS"])
"""


@pytest.fixture
def botbox_caller_labels() -> str:
    return "team=research\npurpose=botbox-memory-proof"


@pytest.fixture
def botbox_memory_project(tmp_path: Path) -> Iterator[Path]:
    if shutil.which("docker") is None:
        pytest.skip("docker is unavailable")
    try:
        available = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=3, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("docker daemon is unavailable")
    if available.returncode != 0:
        pytest.skip("docker daemon is unavailable")

    root = tmp_path / "botbox memory project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(BOTBOX_CONTAINER)
    (root / "hook.py").write_text(HOOK)
    python = shlex.quote(sys.executable)
    (root / "exp" / "experiment.toml").write_text(
        f'command = "{python} script.py"\n'
        f'setup = "{python} hook.py setup"\n'
        f'teardown = "{python} hook.py teardown"\n'
        "memory_interval = 0.2\n"
    )
    try:
        yield root
    finally:
        # --rm handles normal exits; remove our container if a test times out.
        for cidfile in (root / "exp" / "runs").rglob("container.cid"):
            subprocess.run(
                ["docker", "rm", "--force", cidfile.read_text().strip()],
                capture_output=True,
                timeout=10,
                check=False,
            )
