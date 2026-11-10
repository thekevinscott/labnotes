import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui

SCRIPT = (
    "import time\n"
    "for i in range(10):\n"
    "    print(f'out {i}')\n"
    "    time.sleep(0.3)\n"
)


def test_uvx_timeout_keeps_unflushed_python_stdout(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/script.py").write_text(SCRIPT)
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} {root}/exp/script.py"\n'
    )

    term = tui(
        root, "experiments", "exp", "run", "--timeout", "2", unset=("PYTHONUNBUFFERED",)
    )

    expect(term.get_by_text("0 passed, 1 failed.")).to_be_visible(timeout=120)
    expect(term.get_by_text("out 0")).to_be_visible()
    tui.quit(term)
