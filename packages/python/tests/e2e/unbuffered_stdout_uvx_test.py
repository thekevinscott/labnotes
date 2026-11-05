import os
import sys
from pathlib import Path

from conftest import run_uvx_tui

SCRIPT = (
    "import time\n"
    "for i in range(10):\n"
    "    print(f'out {i}')\n"
    "    time.sleep(0.3)\n"
)


def test_uvx_timeout_keeps_unflushed_python_stdout(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/script.py").write_text(SCRIPT)
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} {root}/exp/script.py"\n'
    )
    env = {**os.environ, **uvx}
    env.pop("PYTHONUNBUFFERED", None)

    run_uvx_tui(root, uvx, "experiments", "exp", "run", "--timeout", "2", env=env)

    logs = list(root.glob("exp/runs/*/stdout.log"))
    assert logs, "no run folder"
    assert "out 0" in logs[0].read_text()
