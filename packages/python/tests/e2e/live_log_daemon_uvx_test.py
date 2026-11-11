import shlex
import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui

# Records every stdout/stderr log a run TUI process opens. The daemon and the
# run's own child are excluded by argv, so only the TUI is checked.
RECORD_OPENS = """
import os, sys

def _record(event, args):
    if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    argv = sys.argv
    if "daemon" in argv or "experiments" not in argv:
        return
    path = os.fsdecode(args[0])
    name = os.path.basename(path)
    if "/runs/" in path and name.startswith(("stdout", "stderr")):
        with open(os.environ["LABNOTES_TEST_OPENS"], "a") as found:
            found.write(path + "\\n")

sys.addaudithook(_record)
"""


def test_uvx_run_tui_streams_live_output_from_daemon(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    command = (
        f"{shlex.quote(sys.executable)} -c "
        '"import sys, time\nfor i in range(100): '
        "print('tick', i, flush=True); print('warn', i, file=sys.stderr, flush=True); "
        'time.sleep(0.2)"'
    )
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = '''{command}'''\n"
    )
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "sitecustomize.py").write_text(RECORD_OPENS)
    opens = tmp_path / "opens.txt"
    env = {"PYTHONPATH": str(hooks), "LABNOTES_TEST_OPENS": str(opens)}

    term = tui(root, "experiments", "exp", "run", env=env, cols=160)
    expect(term.get_by_text("1 at a time")).to_be_visible(timeout=60)
    term.key_enter()
    expect(term.get_by_text("tick 3")).to_be_visible()
    expect(term.get_by_text("tick 12")).to_be_visible()
    term.write("t")
    expect(term.get_by_text("warn 20")).to_be_visible()
    tui.stop(term)

    assert list(root.glob("exp/runs/*/stdout.log")), "run wrote no log record"
    read = opens.read_text().splitlines() if opens.exists() else []
    assert read == [], f"run TUI read log files itself: {sorted(set(read))}"
