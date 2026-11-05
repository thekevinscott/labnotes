import json
import os
import subprocess
from pathlib import Path


def test_installed_timeout_removes_the_labeled_container(
    tmp_path: Path, uvx: dict[str, str], fake_docker: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        'continues = false\ncommand = "docker run --rm --label labnotes.run=$LABNOTES_RUN alpine sleep 30"\n'
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
            "--headless",
            "--timeout",
            "2",
        ],
        cwd=root,
        env={**os.environ, **uvx, **fake_docker},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    [record] = root.glob("exp/runs/*/run.json")
    assert json.loads(record.read_text())["ended_by"] == "timeout", result.stdout
    assert not Path(fake_docker["FAKE_DOCKER_STATE"]).exists()
