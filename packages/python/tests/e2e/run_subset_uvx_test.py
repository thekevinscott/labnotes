import json
import os
import subprocess
import sys
from pathlib import Path


def test_uvx_run_takes_several_values_of_one_param(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"command = \"{sys.executable} -c 'pass'\"\n"
        '[params]\nmodel = ["opus", "sonnet", "haiku"]\neffort = ["low", "xhigh"]\n'
    )

    result = subprocess.run(
        [
            "uvx",
            "labnotes",
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
            "--effort=xhigh",
            "--model=opus",
            "--model=haiku",
        ],
        cwd=root,
        env={**os.environ, **uvx},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout
    assert result.stdout.endswith("2 passed, 0 failed.\n"), result.stdout
    cells = sorted(
        (
            json.loads(path.read_text())["params"]
            for path in root.glob("exp/runs/**/run.json")
        ),
        key=json.dumps,
    )
    assert cells == [
        {"effort": "xhigh", "model": "haiku"},
        {"effort": "xhigh", "model": "opus"},
    ]
