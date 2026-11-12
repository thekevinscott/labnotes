import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui

SCRIPT = (
    "import sys, time\n"
    "sys.stdout.write('\\x1b]0;window title\\x07titled\\n')\n"
    "sys.stdout.write('crlf first\\r\\ncrlf second\\r\\n')\n"
    "for i in range(5):\n"
    "    print(f'progress {i}', end='\\r', flush=True)\n"
    "    time.sleep(0.1)\n"
    "print(flush=True)\n"
    "time.sleep(60)\n"
)


def test_uvx_run_shows_carriage_return_output_as_a_terminal_would(
    tmp_path: Path, tui: Tui
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/script.py").write_text(SCRIPT)
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} {root}/exp/script.py"\n'
    )

    term = tui(root, "experiments", "exp", "run", rows=24, cols=80)

    expect(term.get_by_text("titled")).to_be_visible(timeout=60)
    expect(term.get_by_text("progress 4")).to_be_visible(timeout=30)
    expect(term.get_by_text("crlf first")).to_be_visible()
    expect(term.get_by_text("crlf second")).to_be_visible()
    expect(term.get_by_text("0;window title")).not_to_be_visible()
    tui.stop(term)
