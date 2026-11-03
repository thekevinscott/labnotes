import json
import fcntl
import sys
from pathlib import Path

import pytest

from labnotes.cli import main

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
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(root / ".labnotes.toml"), "experiments", "exp", "run", *args])
    assert exit_info.value.code == 0


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
