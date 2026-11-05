import json
import fcntl
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import psutil

from conftest import run_tui_command
from labnotes.daemon.client import daemon_socket
from labnotes.read_config import read_config


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


def test_browse_key_restarts_the_selected_failed_run(terminal, tmp_path: Path) -> None:
    from curtaincall import expect

    root = project(tmp_path, False)
    run(root, "--", "--token", "original")
    before = records(root)
    [failed_id] = [
        run_id for run_id, record in before.items() if record["exit_code"] == 1
    ]
    [passed_id] = [
        run_id for run_id, record in before.items() if record["exit_code"] == 0
    ]
    command = Path(sys.executable).parent / "labnotes"
    term = terminal(
        f"{command} -c {root / '.labnotes.toml'} experiments exp",
        rows=30,
        cols=120,
    )
    expect(term.get_by_text(failed_id)).to_be_visible()
    rows = ["".join(row) for row in term.get_viewable_buffer()]
    failed_row = next(i for i, row in enumerate(rows) if failed_id in row)
    passed_row = next(i for i, row in enumerate(rows) if passed_id in row)
    if failed_row > passed_row:
        term.key_down()
    term.write("r")
    expect(term.get_by_text("Restarted")).to_be_visible(timeout=10)
    assert [
        json.loads(line)["m"]
        for line in (root / "launches.jsonl").read_text().splitlines()
    ] == ["a", "b", "a"]
    term.key_ctrl_c()
    term.wait()


def test_browse_restart_finishes_after_tui_is_killed(terminal, tmp_path: Path) -> None:
    from curtaincall import expect

    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "marker").write_text("")
    (root / "script.py").write_text(
        "import sys, time\nfrom pathlib import Path\n"
        "if Path('marker').exists():\n"
        "    Path('marker').unlink()\n    sys.exit(1)\n"
        "time.sleep(2)\n"
    )
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\ncontinues = false\nretries = 0\n'
    )
    run(root)
    [failed_id] = records(root)
    command = Path(sys.executable).parent / "labnotes"
    term = terminal(
        f"{command} -c {root / '.labnotes.toml'} experiments exp", rows=30, cols=120
    )
    try:
        expect(term.get_by_text(failed_id)).to_be_visible()
        term.write("r")
        for _ in range(100):
            current = records(root)
            new_ids = current.keys() - {failed_id}
            if new_ids and current[next(iter(new_ids))].get("pid"):
                break
            time.sleep(0.05)
        assert len(new_ids) == 1
        assert daemon_socket(read_config(root / ".labnotes.toml"), "exp") is not None
        term.kill()
        for _ in range(100):
            current = records(root)
            restarted = current[next(iter(new_ids))]
            if restarted.get("ended"):
                break
            time.sleep(0.05)
        assert restarted["exit_code"] == 0
    finally:
        term.kill()


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


def test_browse_explains_when_selected_run_is_held(terminal, tmp_path: Path) -> None:
    from curtaincall import expect

    root = project(tmp_path, False)
    run(root, "--", "--token", "original")
    before = records(root)
    [failed_id] = [
        run_id for run_id, record in before.items() if record["exit_code"] == 1
    ]
    [passed_id] = [
        run_id for run_id, record in before.items() if record["exit_code"] == 0
    ]
    lock_path = (
        next((root / "exp/runs").rglob(f"{failed_id}/run.json")).parent / "run.lock"
    )
    command = Path(sys.executable).parent / "labnotes"
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        term = terminal(
            f"{command} -c {root / '.labnotes.toml'} experiments exp",
            rows=30,
            cols=120,
        )
        expect(term.get_by_text(failed_id)).to_be_visible()
        rows = ["".join(row) for row in term.get_viewable_buffer()]
        if next(i for i, row in enumerate(rows) if failed_id in row) > next(
            i for i, row in enumerate(rows) if passed_id in row
        ):
            term.key_down()
        term.write("r")
        expect(term.get_by_text("held by another run")).to_be_visible()
        term.key_ctrl_c()
        term.wait()
    assert len(records(root)) == 2
