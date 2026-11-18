import json
import shlex
import sys
from collections.abc import Iterator
from pathlib import Path

import psutil
import pytest
from curtaincall import Terminal, expect

from conftest import run_tui_command


@pytest.fixture(autouse=True)
def cleanup_daemons(tmp_path: Path) -> Iterator[None]:
    yield
    config = str(tmp_path / ".labnotes.toml")
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


SCRIPT = """
import sys
from pathlib import Path

if Path("fail-once").exists():
    Path("fail-once").unlink()
    print("checkpoint lost", flush=True)
    sys.exit(1)
"""


def project(root: Path) -> Path:
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(SCRIPT)
    (root / "fail-once").write_text("")
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\n'
        'continues = true\nretries = 0\n[params]\nm = ["a"]\n'
    )
    return root


def test_capped_run_keeps_a_row_and_restarts_with_r(terminal, tmp_path: Path) -> None:
    root = project(tmp_path)
    assert run_tui_command(root, ["experiments", "exp", "run"]) == 0
    [record_path] = (root / "exp/runs").rglob("run.json")
    run = record_path.parent.name

    labnotes = Path(sys.executable).parent / "labnotes"
    term: Terminal = terminal(
        f"{labnotes} -c {shlex.quote(str(root / '.labnotes.toml'))} experiments exp run",
        rows=30,
        cols=200,
    )
    expect(term.get_by_text(run)).to_be_visible(timeout=120)
    expect(term.get_by_text("✗ capped 1/0")).to_be_visible()
    expect(term.get_by_text("0 passed, 1 failed.")).to_be_visible()

    term.key_enter()
    expect(term.get_by_text("checkpoint lost")).to_be_visible(timeout=30)
    term.key_escape()
    expect(term.get_by_text("0 passed, 1 failed.")).to_be_visible()
    term.write("r")
    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=60)
    record = json.loads(record_path.read_text())
    assert [i["exit_code"] for i in record["invocations"]] == [1, 0]
    assert list((root / "exp/runs").rglob("run.json")) == [record_path]
    term.key_ctrl_c()
