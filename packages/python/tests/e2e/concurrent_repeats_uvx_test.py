import os
import subprocess
import sys
import time
from pathlib import Path


def test_uvx_overlapping_clients_do_not_exceed_repeats(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "sleep.py").write_text(
        "import pathlib, time\n"
        "pathlib.Path('started').write_text('yes')\n"
        "time.sleep(1.5)\n"
    )
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} sleep.py"\nrepeats = 3\n'
    )
    command = [
        "uvx",
        "labnotes",
        "-c",
        str(root / ".labnotes.toml"),
        "experiments",
        "exp",
        "run",
        "--headless",
        "--concurrency",
        "1",
    ]
    environment = {**os.environ, **uvx}
    first = subprocess.Popen(
        command,
        cwd=root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    second = None
    try:
        for _ in range(200):
            if (root / "started").exists():
                break
            time.sleep(0.02)
        else:
            raise AssertionError("first client never started")
        second = subprocess.Popen(
            command,
            cwd=root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        second_output, _ = second.communicate(timeout=15)
        first_output, _ = first.communicate(timeout=15)
        assert first.returncode == 0, first_output
        assert second.returncode == 0, second_output
        assert len(list((root / "exp/runs").glob("*/run.json"))) == 3
        assert second_output.endswith("0 passed, 0 failed.\n")
    finally:
        for process in (first, second):
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
