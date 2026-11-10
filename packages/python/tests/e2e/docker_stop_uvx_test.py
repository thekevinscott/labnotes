import json
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_installed_timeout_removes_the_labeled_container(
    tmp_path: Path, tui: Tui, fake_docker: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        'continues = false\ncommand = "docker run --rm --label labnotes.run=$LABNOTES_RUN alpine sleep 30"\n'
    )

    term = tui(root, "experiments", "exp", "run", "--timeout", "2", env=fake_docker)

    expect(term.get_by_text("0 passed, 1 failed.")).to_be_visible(timeout=120)
    tui.quit(term)
    [record] = root.glob("exp/runs/*/run.json")
    assert json.loads(record.read_text())["ended_by"] == "timeout"
    assert not Path(fake_docker["FAKE_DOCKER_STATE"]).exists()
