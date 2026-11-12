import json
import fcntl
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import psutil

from conftest import run_tui_command


@pytest.fixture(autouse=True)
def cleanup_daemons(tmp_path: Path) -> Iterator[None]:
    yield
    config = str(tmp_path / ".labnotes.toml")
    alternate = str(tmp_path / "project" / ".labnotes.toml")
    owners = [
        process
        for process in psutil.process_iter(["cmdline"])
        if "daemon" in (process.info["cmdline"] or [])
        and (
            config in (process.info["cmdline"] or [])
            or alternate in (process.info["cmdline"] or [])
        )
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
import json
import sys
from pathlib import Path

value = sys.argv[sys.argv.index("--m") + 1]
token = sys.argv[sys.argv.index("--token") + 1]
with Path("launches.jsonl").open("a") as log:
    log.write(json.dumps({"m": value, "token": token}) + "\\n")
if value == "a" and Path("fail-once").exists():
    Path("fail-once").unlink()
    sys.exit(1)
"""


def project(root: Path, continues: bool) -> Path:
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(SCRIPT)
    (root / "fail-once").write_text("")
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\n'
        f"continues = {str(continues).lower()}\nretries = 0\n"
        '[params]\nm = ["a", "b"]\n'
    )
    return root


def run(root: Path, *args: str) -> None:
    assert run_tui_command(root, ["experiments", "exp", "run", *args]) == 0


def records(root: Path) -> dict[str, dict[str, object]]:
    return {
        path.parent.name: json.loads(path.read_text())
        for path in (root / "exp/runs").rglob("run.json")
    }


@pytest.mark.parametrize("continues", [False, True])
def test_restarts_only_one_failed_run_with_its_recorded_args(
    tmp_path: Path, continues: bool
) -> None:
    root = project(tmp_path, continues)
    run(root, "--", "--token", "original")
    before = records(root)
    [failed_id] = [
        run_id for run_id, record in before.items() if record["exit_code"] == 1
    ]

    run(root, "--run-id", failed_id)

    launched = [
        json.loads(line) for line in (root / "launches.jsonl").read_text().splitlines()
    ]
    assert launched == [
        {"m": "a", "token": "original"},
        {"m": "b", "token": "original"},
        {"m": "a", "token": "original"},
    ]
    after = records(root)
    if continues:
        assert set(after) == set(before)
        assert len(after[failed_id]["invocations"]) == 2
    else:
        assert len(after) == len(before) + 1
        [new_id] = after.keys() - before.keys()
        assert after[new_id]["params"] == {"m": "a"}
        assert after[new_id]["args"] == ["--token", "original"]


def test_rejects_a_passed_or_held_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = project(tmp_path, False)
    run(root, "--", "--token", "original")
    before = records(root)
    [passed_id] = [
        run_id for run_id, record in before.items() if record["exit_code"] == 0
    ]
    [failed_id] = [
        run_id for run_id, record in before.items() if record["exit_code"] == 1
    ]
    with pytest.raises(AssertionError):
        run(root, "--run-id", passed_id)
    assert "has not failed" in capsys.readouterr().err

    lock_path = (
        next((root / "exp/runs").rglob(f"{failed_id}/run.json")).parent / "run.lock"
    )
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(AssertionError):
            run(root, "--run-id", failed_id)
        assert "held by another run" in capsys.readouterr().err
    assert len(records(root)) == 2


@pytest.mark.parametrize(
    ("continues", "summary"),
    [
        (False, "2 passed, 0 failed. 1 retried. Ctrl-C"),
        (True, "2 passed, 0 failed. Ctrl-C"),
    ],
)
def test_live_view_shows_the_restarted_run(
    terminal, tmp_path: Path, continues: bool, summary: str
) -> None:
    from curtaincall import expect

    root = project(tmp_path, continues)
    command = Path(sys.executable).parent / "labnotes"
    term = terminal(
        f"{command} -c {root / '.labnotes.toml'} experiments exp run -- --token t",
        rows=30,
        cols=120,
    )
    expect(term.get_by_text("1 passed, 1 failed.")).to_be_visible(timeout=30)
    term.write("r")
    expect(term.get_by_text(summary)).to_be_visible(timeout=30)
    for run_id in records(root):
        expect(term.get_by_text(run_id)).to_be_visible()
    term.key_ctrl_c()
    term.wait()
