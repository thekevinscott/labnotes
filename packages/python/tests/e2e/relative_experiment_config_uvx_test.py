import json
import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_uvx_run_uses_a_relative_experiment_config_in_tui(
    tmp_path: Path, tui: Tui
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / "alt").mkdir()
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text('command = "false"\n')
    (root / "alt/experiment.toml").write_text(
        f"command = \"{sys.executable} -c 'print(317)'\"\ncontinues = false\n"
    )

    term = tui(root, "experiments", "exp", "run", "-e", "alt/experiment.toml")

    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=120)
    expect(term.get_by_text("317")).to_be_visible()
    tui.quit(term)
    [record] = [
        json.loads(path.read_text()) for path in root.glob("exp/runs/*/run.json")
    ]
    assert record["exit_code"] == 0
