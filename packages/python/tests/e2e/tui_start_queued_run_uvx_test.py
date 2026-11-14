import json
import re
import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_installed_tui_starts_a_queued_run_now(tmp_path: Path, tui: Tui) -> None:
    (tmp_path / "exp").mkdir()
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp/experiment.toml").write_text(
        "continues = false\n"
        f"command = \"{sys.executable} -c 'import time; time.sleep(4)'\"\n"
        "[params]\nm = ['a', 'b', 'c']\n"
    )
    term = tui(tmp_path, "experiments", "exp", "run", cols=120)

    expect(term.get_by_text(re.compile(r"--m a +[|/\\-]"))).to_be_visible(timeout=30)
    expect(term.get_by_text("Start now")).to_be_visible()
    term.key_down()
    term.key_down()
    term.write("s")
    expect(term.get_by_text(re.compile(r"--m c +[|/\\-]"))).to_be_visible()
    expect(term.get_by_text(re.compile(r"--m a +[|/\\-]"))).to_be_visible()
    expect(term.get_by_text(re.compile(r"--m b +○"))).to_be_visible()
    expect(term.get_by_text("3 passed, 0 failed")).to_be_visible(timeout=30)
    tui.check(term)
    records = [
        json.loads(path.read_text()) for path in tmp_path.glob("exp/runs/*/run.json")
    ]
    assert sorted(record["params"]["m"] for record in records) == ["a", "b", "c"]
    tui.quit(term)
