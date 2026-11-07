import os
import sys
from collections.abc import Iterator
from pathlib import Path

import psutil
import pytest
from curtaincall import expect

SCRIPT = (
    "import sys, time\n"
    "for word in ['one', 'two', 'three']:\n"
    "    print(f'out {word}', flush=True)\n"
    "for word in ['one', 'two']:\n"
    "    print(f'err {word}', file=sys.stderr, flush=True)\n"
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


def test_uvx_run_shows_stdout_and_stderr_in_separate_tabs(
    terminal, tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/script.py").write_text(SCRIPT)
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} {root}/exp/script.py"\n'
    )

    term = terminal(
        f"uvx labnotes -c {root / '.labnotes.toml'} experiments exp run",
        rows=30,
        cols=120,
        env={**os.environ, **uvx},
    )

    expect(term.get_by_text("stdout (3)")).to_be_visible(timeout=60)
    expect(term.get_by_text("stderr (2)")).to_be_visible()
    expect(term.get_by_text("out three")).to_be_visible()
    expect(term.get_by_text("err one")).not_to_be_visible()
    term.write("t")
    expect(term.get_by_text("err two")).to_be_visible()
    expect(term.get_by_text("out one")).not_to_be_visible()
    term.key_ctrl_c()
    term.write("s")
    term.wait()
