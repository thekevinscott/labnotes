import json
import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui

SCRIPT = """
import sys
from pathlib import Path

if Path("fail-once").exists():
    Path("fail-once").unlink()
    print("checkpoint lost", flush=True)
    sys.exit(1)
"""


def test_uvx_shows_a_capped_run_and_restarts_it(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(SCRIPT)
    (root / "fail-once").write_text("")
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\n'
        'continues = true\nretries = 0\n[params]\nm = ["a"]\n'
    )

    term = tui(root, "experiments", "exp", "run")
    expect(term.get_by_text("0 passed, 1 failed.")).to_be_visible(timeout=120)
    tui.quit(term)
    [record_path] = (root / "exp/runs").rglob("run.json")

    term = tui(root, "experiments", "exp", "run")
    expect(term.get_by_text("✗ capped 1/0")).to_be_visible(timeout=120)
    expect(term.get_by_text(record_path.parent.name)).to_be_visible()
    expect(term.get_by_text("0 passed, 1 failed.")).to_be_visible()
    term.key_enter()
    expect(term.get_by_text("checkpoint lost")).to_be_visible(timeout=30)
    term.key_escape()
    expect(term.get_by_text("0 passed, 1 failed.")).to_be_visible()
    term.write("r")

    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=60)
    tui.quit(term)
    record = json.loads(record_path.read_text())
    assert [i["exit_code"] for i in record["invocations"]] == [1, 0]
    assert list((root / "exp/runs").rglob("run.json")) == [record_path]
