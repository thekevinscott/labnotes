import sys
from pathlib import Path

import psutil
from curtaincall import expect

from conftest import Tui

SCRIPT = (
    "import sys, time\n"
    "sys.stdout.write(''.join(f'line {n}\\n' for n in range(2_000_000)))\n"
    "sys.stdout.flush()\n"
    "time.sleep(60)\n"
)


def test_uvx_run_follows_a_large_log_without_holding_it(
    tmp_path: Path, tui: Tui
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/script.py").write_text(SCRIPT)
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} {root}/exp/script.py"\n'
    )

    term = tui(root, "experiments", "exp", "run", cols=120)

    expect(term.get_by_text("stdout (2000000)")).to_be_visible(timeout=60)
    expect(term.get_by_text("line 1999999")).to_be_visible()
    expect(term.get_by_text("line 0")).not_to_be_visible()
    viewers = [
        process.info["memory_info"].rss
        for process in psutil.process_iter(["cmdline", "memory_info"])
        if str(root / ".labnotes.toml") in (process.info["cmdline"] or [])
        and "run" in (process.info["cmdline"] or [])
    ]
    # Holding all 2M lines took about 300 MB; a window of them stays near 80 MB.
    assert 0 < max(viewers) < 150_000_000
    tui.stop(term)
