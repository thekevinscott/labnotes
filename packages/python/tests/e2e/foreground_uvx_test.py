import json
import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_uvx_run_completes_through_tui(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = \"{sys.executable} -c 'print(1)'\"\n"
    )

    term = tui(root, "experiments", "exp", "run")

    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=120)
    tui.quit(term)
    [record] = [
        json.loads(path.read_text()) for path in root.glob("exp/runs/*/run.json")
    ]
    assert record["exit_code"] == 0
