import os
import shlex
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

OLD_VERSION = "0.0.135"
WAIT = """
import sys
import time
from pathlib import Path

for _ in range(1200):
    if Path("release").exists():
        print("released")
        break
    time.sleep(0.1)
"""
LABELS = """
import os
from pathlib import Path

Path("labels.txt").write_text(os.environ["BOTBOX_LABELS"])
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def labnotes(root: Path, name: str, *version: str) -> list[str]:
    source = ["--from", f"labnotes=={version[0]}"] if version else []
    config = str(root / ".labnotes.toml")
    return ["uvx", *source, "labnotes", "-c", config, "experiments", name, "run"]


def wait_for(found: Callable[[], bool], what: str) -> None:
    for _ in range(600):
        if found():
            return
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {what}.")


def test_a_new_version_runs_beside_an_older_daemon_and_its_live_run(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    python = shlex.quote(sys.executable)
    write(root / "wait.py", WAIT)
    write(root / "labels.py", LABELS)
    write(root / "slow" / "experiment.toml", f"command = '{python} wait.py'\n")
    write(
        root / "fast" / "experiment.toml",
        f"command = '{python} labels.py'\nsetup = 'true'\nteardown = 'true'\n",
    )
    write(
        root / ".labnotes.toml",
        '[experiments]\npath = "{experiment}"\n'
        '[experiment.env]\nBOTBOX_LABELS = "labnotes.run={run_dir}"\n',
    )
    old_env = {**os.environ, "UV_NO_CONFIG": "1"}
    old_env.pop("BOTBOX_LABELS", None)
    old = subprocess.Popen(
        labnotes(root, "slow", OLD_VERSION),
        cwd=root,
        env=old_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for(lambda: any(root.glob("slow/runs/*/run.json")), "the old run")
        write(root / ".labnotes.toml", '[experiments]\npath = "{experiment}"\n')

        new = subprocess.run(
            labnotes(root, "fast"),
            cwd=root,
            env={**old_env, **uvx},
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert new.returncode == 0, new.stdout + new.stderr
        assert "1 passed, 0 failed." in new.stdout
        assert old.poll() is None
        [record] = root.glob("fast/runs/*/run.json")
        assert (root / "labels.txt").read_text() == (
            f"labnotes.run={record.parent.resolve()}"
        )
        write(root / "release", "")
        out, _ = old.communicate(timeout=60)
        assert old.returncode == 0, out
        assert "1 passed, 0 failed." in out
        [slow] = root.glob("slow/runs/*/stdout.log")
        assert slow.read_text().strip() == "released"
    finally:
        old.kill()
        old.wait()
