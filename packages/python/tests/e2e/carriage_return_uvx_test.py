import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui

SCRIPT = (
    "import sys, time\n"
    "sys.stdout.write('crlf first\\r\\ncrlf second\\r\\n')\n"
    "for i in range(10):\n"
    "    sys.stdout.write(f'step {i}\\r')\n"
    "sys.stdout.write('\\n')\n"
    "for i in range(4):\n"
    "    sys.stdout.write(f'loading {i}\\r')\n"
    "sys.stdout.flush()\n"
    "time.sleep(60)\n"
)


def test_uvx_run_shows_lines_that_end_in_a_carriage_return(
    tmp_path: Path, tui: Tui
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/script.py").write_text(SCRIPT)
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} {root}/exp/script.py"\n'
    )

    term = tui(root, "experiments", "exp", "run")

    expect(term.get_by_text("crlf first")).to_be_visible(timeout=60)
    expect(term.get_by_text("crlf second")).to_be_visible()
    expect(term.get_by_text("step 9")).to_be_visible()
    expect(term.get_by_text("step 8")).not_to_be_visible()
    expect(term.get_by_text("loading 3")).to_be_visible()
    tui.stop(term)
