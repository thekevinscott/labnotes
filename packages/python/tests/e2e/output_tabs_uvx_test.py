import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui

SCRIPT = (
    "import sys, time\n"
    "for word in ['one', 'two', 'three']:\n"
    "    print(f'out {word}', flush=True)\n"
    "for word in ['one', 'two']:\n"
    "    print(f'err {word}', file=sys.stderr, flush=True)\n"
    "time.sleep(60)\n"
)


def test_uvx_run_shows_stdout_and_stderr_in_separate_tabs(
    tmp_path: Path, tui: Tui
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/script.py").write_text(SCRIPT)
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} {root}/exp/script.py"\n'
    )

    term = tui(root, "experiments", "exp", "run", rows=30, cols=120)

    expect(term.get_by_text("stdout (3)")).to_be_visible(timeout=60)
    expect(term.get_by_text("stderr (2)")).to_be_visible()
    expect(term.get_by_text("out three")).to_be_visible()
    expect(term.get_by_text("err one")).not_to_be_visible()
    term.write("t")
    expect(term.get_by_text("err two")).to_be_visible()
    expect(term.get_by_text("out one")).not_to_be_visible()
    tui.stop(term)
