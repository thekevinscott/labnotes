import json
import os
from pathlib import Path

from conftest import run_uvx_tui


def test_installed_timeout_removes_the_labeled_container(
    tmp_path: Path, uvx: dict[str, str], fake_docker: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        'continues = false\ncommand = "docker run --rm --label labnotes.run=$LABNOTES_RUN alpine sleep 30"\n'
    )
    result = run_uvx_tui(
        root,
        uvx,
        "experiments",
        "exp",
        "run",
        "--timeout",
        "2",
        env={**os.environ, **fake_docker},
    )
    [record] = root.glob("exp/runs/*/run.json")
    assert json.loads(record.read_text())["ended_by"] == "timeout", result.stdout
    assert not Path(fake_docker["FAKE_DOCKER_STATE"]).exists()
