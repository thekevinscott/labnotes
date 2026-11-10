import json
import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_uvx_run_takes_several_values_of_one_param(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = \"{sys.executable} -c 'pass'\"\n"
        '[params]\nmodel = ["opus", "sonnet", "haiku"]\neffort = ["low", "xhigh"]\n'
    )

    term = tui(
        root,
        *["experiments", "exp", "run", "--effort=xhigh"],
        *["--model=opus", "--model=haiku"],
    )

    expect(term.get_by_text("2 passed, 0 failed.")).to_be_visible(timeout=120)
    expect(term.get_by_text("--model opus")).to_be_visible()
    expect(term.get_by_text("--model haiku")).to_be_visible()
    expect(term.get_by_text("sonnet")).not_to_be_visible()
    expect(term.get_by_text("--effort low")).not_to_be_visible()
    tui.quit(term)
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
