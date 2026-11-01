import json
import os
import subprocess
import sys
from pathlib import Path


def test_uvx_run_gives_run_dir_env_to_the_run_but_not_to_setup(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text(
        '[experiments]\npath = "{experiment}"\n[experiment.env]\nLABEL = "{run_dir}"\n'
    )
    (root / "capture.py").write_text(
        "import json, os, sys\n"
        'with open("journal.jsonl", "a") as journal:\n'
        '    journal.write(json.dumps([sys.argv[1], os.environ.get("LABEL")]) + "\\n")\n'
    )
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} capture.py run"\n'
        f'setup = "{sys.executable} capture.py setup"\n'
    )
    env = {key: value for key, value in os.environ.items() if key != "LABEL"}

    result = subprocess.run(
        [
            "uvx",
            "labnotes",
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
        ],
        cwd=root,
        env={**env, **uvx},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    [folder] = (root / "exp/runs").iterdir()
    assert [
        json.loads(line) for line in (root / "journal.jsonl").read_text().splitlines()
    ] == [["setup", None], ["run", str(folder.resolve())]]
