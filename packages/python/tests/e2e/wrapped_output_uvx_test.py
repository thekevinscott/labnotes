import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import psutil
import pytest
from curtaincall import expect

SCRIPT = (
    "import pathlib, sys, time\n"
    "print(''.join(f'line {n}\\n' for n in range(60)) + 'y' * 300 + '\\ntail end')\n"
    "sys.stdout.flush()\n"
    "while not (pathlib.Path(sys.argv[1]) / 'more').exists():\n"
    "    time.sleep(0.1)\n"
    "print('after more', flush=True)\n"
    "time.sleep(60)\n"
)


@pytest.fixture(autouse=True)
def cleanup_daemon(tmp_path: Path) -> Iterator[None]:
    yield
    config = str(tmp_path / "project" / ".labnotes.toml")
    owners = [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (process.info["cmdline"] or [])
        and "daemon" in (process.info["cmdline"] or [])
    ]
    for process in owners:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(owners, timeout=15)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass


def test_uvx_run_wraps_output_and_follows_it_from_the_bottom(
    terminal, tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/script.py").write_text(SCRIPT)
    (root / "exp/experiment.toml").write_text(
        "continues = false\n"
        f'command = "{sys.executable} {root}/exp/script.py {tmp_path}"\n'
    )

    term = terminal(
        f"uvx labnotes -c {root / '.labnotes.toml'} experiments exp run",
        rows=24,
        cols=80,
        env={**os.environ, **uvx},
    )

    expect(term.get_by_text("tail end")).to_be_visible(timeout=60)
    expect(term.get_by_text("line 0")).not_to_be_visible()
    rows = ["".join(row) for row in term.get_viewable_buffer()]
    assert sum("y" * 70 in row for row in rows) >= 3
    for _ in range(25):
        term.key_up()
    expect(term.get_by_text("tail end")).not_to_be_visible()
    (tmp_path / "more").touch()
    time.sleep(2)
    expect(term.get_by_text("after more")).not_to_be_visible()
    for _ in range(40):
        term.key_down()
    expect(term.get_by_text("after more")).to_be_visible()
    term.key_ctrl_c()
    term.write("s")
    term.wait()
