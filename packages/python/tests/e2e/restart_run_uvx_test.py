import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_uvx_restarts_only_the_selected_failed_run(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        "m = sys.argv[sys.argv.index('--m') + 1]\n"
        "with Path('launches.txt').open('a') as log: log.write(m + '\\n')\n"
        "if m == 'a' and Path('fail-once').exists():\n"
        "    Path('fail-once').unlink()\n    sys.exit(1)\n"
    )
    (root / "fail-once").write_text("")
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\n'
        'continues = false\nretries = 0\n[params]\nm = ["a", "b"]\n'
    )

    term = tui(root, "experiments", "exp", "run")
    expect(term.get_by_text("1 passed, 1 failed.")).to_be_visible(timeout=120)
    expect(term.get_by_text("✗ exited 1")).to_be_visible()
    term.write("r")

    expect(term.get_by_text("2 passed, 0 failed. 1 retried.")).to_be_visible(timeout=60)
    runs = [path.parent.name for path in (root / "exp/runs").rglob("run.json")]
    assert len(runs) == 3
    for run in runs:
        expect(term.get_by_text(run)).to_be_visible()
    tui.quit(term)
    assert (root / "launches.txt").read_text().splitlines() == ["a", "b", "a"]
