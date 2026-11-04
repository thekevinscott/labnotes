import asyncio
import fcntl
import json
import os
import shlex
import sys
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest

from labnotes.cli import main
from labnotes.models import Controls
from labnotes.read_config import read_config
from labnotes.runner.prepare_experiment import prepare_experiment
from labnotes.runner.run_experiment import run_experiment

# Each launch adds an x to state.txt in its run folder, then exits with the
# next code in codes.txt (0 once they run out).
SCRIPT = """
import os
import sys
from pathlib import Path

state = Path(os.environ["LABNOTES_RUN"]) / "state.txt"
seen = state.read_text() if state.exists() else ""
state.write_text(seen + "x")
print(f"launch {len(seen) + 1}")
codes = Path("codes.txt")
left = codes.read_text().split()
codes.write_text(" ".join(left[1:]))
sys.exit(int(left[0]) if left else 0)
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_project(
    root: Path, codes: str, settings: str = "continues = true\n", cells: str = '"a"'
) -> Path:
    write(root / ".labnotes.toml", "")
    write(root / "script.py", SCRIPT)
    write(root / "codes.txt", codes)
    write(
        root / "exp" / "experiment.toml",
        f'command = "{sys.executable} script.py"\n'
        f"{settings}[params]\nm = [{cells}]\n",
    )
    return root


def labnotes(root: Path, argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(root / ".labnotes.toml"), *argv])
    return exit_info.value.code


def run(root: Path) -> None:
    assert labnotes(root, ["experiments", "exp", "run"]) == 0


def folders(root: Path) -> dict[Path, dict[str, Any]]:
    return {
        path.parent: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((root / "exp" / "runs").glob("**/run.json"))
    }


def logs(folder: Path, stream: str = "stdout") -> list[str]:
    return [path.read_text() for path in sorted(folder.glob(f"{stream}-*.txt"))]


def add_run(root: Path, name: str, **fields: object) -> Path:
    folder = root / "exp" / "runs" / name
    record = {
        "params": {"m": "a"},
        "created": "2026-10-17T00:00:00Z",
        "ended": "2026-10-17T01:00:00Z",
        "exit_code": 1,
        "error": None,
        **fields,
    }
    write(folder / "run.json", json.dumps(record))
    write(folder / "state.txt", "x")
    return folder


def test_a_failed_run_continues_in_its_own_folder(tmp_path: Path) -> None:
    root = make_project(tmp_path, "1", cells='"a", "b"')

    run(root)
    [failed] = [f for f, r in folders(root).items() if r["exit_code"] == 1]
    write(failed / "checkpoint.txt", "step 20")
    run(root)

    recorded = folders(root)
    assert len(recorded) == 2
    record = recorded[failed]
    assert record["exit_code"] == 0
    assert record["ended_by"] is None
    assert [i["exit_code"] for i in record["invocations"]] == [1, 0]
    assert all(i["started"] and i["ended"] for i in record["invocations"])
    assert (failed / "state.txt").read_text() == "xx"
    assert (failed / "checkpoint.txt").read_text() == "step 20"
    assert logs(failed) == ["launch 1\n", "launch 2\n"]
    assert len(logs(failed, "stderr")) == 2
    assert (failed / "run.lock").exists()


def test_several_failed_runs_in_a_cell_each_continue_once(tmp_path: Path) -> None:
    root = make_project(tmp_path, "0 1 1", settings="continues = true\nrepeats = 3\n")

    run(root)
    run(root)

    recorded = folders(root)
    assert len(recorded) == 3
    tries = sorted(
        [i["exit_code"] for i in r["invocations"]] for r in recorded.values()
    )
    assert tries == [[0], [1, 0], [1, 0]]
    assert sorted((f / "state.txt").read_text() for f in recorded) == ["x", "xx", "xx"]


def test_a_run_that_fails_again_continues_again(tmp_path: Path) -> None:
    root = make_project(tmp_path, "1 2")

    run(root)
    run(root)
    run(root)

    [record] = folders(root).values()
    assert [i["exit_code"] for i in record["invocations"]] == [1, 2, 0]


def test_failed_run_gives_up_after_two_retries_and_explicit_restart_works(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(tmp_path, "1 1 1 1", settings="continues = true\nretries = 2\n")
    for _ in range(3):
        run(root)
    [(folder, record)] = folders(root).items()
    before = (folder / "run.json").read_bytes()

    run(root)
    output = capsys.readouterr().out
    assert "1 cell gave up after 2 retries" in output
    assert list(folders(root)) == [folder]
    assert (folder / "run.json").read_bytes() == before
    assert len(record["invocations"]) == 3
    assert (folder / "state.txt").read_text() == "xxx"

    assert labnotes(root, ["experiments", "exp", "run", "--run-id", folder.name]) == 0
    assert len(folders(root)[folder]["invocations"]) == 4


def test_invocations_stopped_by_hand_do_not_spend_retries(tmp_path: Path) -> None:
    root = make_project(tmp_path, "0", settings="continues = true\nretries = 1\n")
    stopped = {"ended": "2026-10-17T00:30:00Z", "exit_code": -15, "ended_by": "stop"}
    folder = add_run(
        root,
        "old",
        invocations=[stopped, stopped, stopped, {"exit_code": 1, "ended_by": None}],
    )

    run(root)

    assert list(folders(root)) == [folder]
    assert len(folders(root)[folder]["invocations"]) == 5


def test_args_and_commit_are_recorded_per_invocation(tmp_path: Path) -> None:
    root = make_project(tmp_path, "1")

    run(root)
    assert labnotes(root, ["experiments", "exp", "run", "--", "--memory", "24g"]) == 0

    [record] = folders(root).values()
    first, second = record["invocations"]
    assert first["args"] == []
    assert second["args"] == ["--memory", "24g"]
    assert record["args"] == ["--memory", "24g"]
    assert {"git", "ended_by"} <= first.keys()


def test_each_invocation_records_its_labnotes_version_and_command_line(
    tmp_path: Path,
) -> None:
    root = make_project(tmp_path, "1")
    config = ["-c", str(root / ".labnotes.toml")]
    later = ["experiments", "exp", "run", "--m=a", "--", "--memory", "24g"]

    run(root)
    assert labnotes(root, later) == 0

    [record] = folders(root).values()
    first, second = record["invocations"]
    command = shlex.join(["labnotes", *config, *later])
    assert first["labnotes_command"] == shlex.join(
        ["labnotes", *config, "experiments", "exp", "run"]
    )
    assert second["labnotes_command"] == command
    assert record["labnotes_command"] == command
    assert first["labnotes_version"] == version("labnotes")
    assert second["labnotes_version"] == version("labnotes")
    assert record["labnotes_version"] == version("labnotes")


def run_now(root: Path) -> list[dict[str, object]]:
    config = read_config(root / ".labnotes.toml")
    events: list[dict[str, object]] = []

    async def go() -> list[dict[str, object]]:
        experiment, concurrency = await prepare_experiment(config, "exp", None, None)

        def listen(controls: Controls) -> None:
            controls.finish()

        return await run_experiment(
            config,
            "exp",
            experiment,
            concurrency,
            events.append,
            listen,
            retry_seconds=0.01,
        )

    asyncio.run(go())
    return events


def test_an_exit_75_retry_runs_again_in_the_same_folder(tmp_path: Path) -> None:
    root = make_project(tmp_path, "75")

    run_now(root)

    [(folder, record)] = folders(root).items()
    assert [i["exit_code"] for i in record["invocations"]] == [75, 0]
    assert "retry_of" not in record
    assert (folder / "state.txt").read_text() == "xx"


@pytest.fixture
def held_lock(tmp_path: Path) -> Iterator[Path]:
    folder = tmp_path / "exp" / "runs" / "held"
    folder.mkdir(parents=True)
    with (folder / "run.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield folder


def test_a_running_run_nobody_holds_is_marked_lost_and_continued(
    tmp_path: Path,
) -> None:
    root = make_project(tmp_path, "", settings="continues = true\nrepeats = 2\n")
    # The pid is alive (this test); only the lock says the run is dead.
    dead = add_run(
        root,
        "dead",
        ended=None,
        exit_code=None,
        pid=os.getpid(),
        invocations=[{"started": "2026-10-17T00:00:00Z", "ended": None}],
    )
    write(dead / "run.lock", "")

    run(root)

    recorded = folders(root)
    assert len(recorded) == 2
    record = recorded[dead]
    first, second = record["invocations"]
    assert first["ended_by"] == "lost"
    assert first["ended"] is not None
    assert second["exit_code"] == 0
    assert (dead / "state.txt").read_text() == "xx"


def test_a_locked_run_is_left_alone(tmp_path: Path, held_lock: Path) -> None:
    root = make_project(tmp_path, "")
    add_run(root, held_lock.name)

    run(root)

    recorded = folders(root)
    assert len(recorded) == 1
    assert "invocations" not in recorded[held_lock]
    assert (held_lock / "state.txt").read_text() == "x"


@pytest.mark.parametrize("continues", [False, True])
def test_a_held_run_fills_its_repeat_slot_and_appears_in_the_plan(
    tmp_path: Path,
    held_lock: Path,
    capsys: pytest.CaptureFixture[str],
    continues: bool,
) -> None:
    root = make_project(
        tmp_path, "", settings=f"continues = {str(continues).lower()}\n"
    )
    add_run(root, held_lock.name, ended=None, exit_code=None)

    run(root)

    assert list(folders(root)) == [held_lock]
    assert "held by another run" in capsys.readouterr().out


def test_a_passed_and_a_held_run_fill_both_repeat_slots(
    tmp_path: Path, held_lock: Path
) -> None:
    root = make_project(tmp_path, "", settings="continues = false\nrepeats = 2\n")
    add_run(root, "passed", exit_code=0)
    add_run(root, held_lock.name, ended=None, exit_code=None)

    run(root)

    assert set(folders(root)) == {held_lock, root / "exp/runs/passed"}


def test_an_unheld_running_record_is_lost_and_planned_again_without_continues(
    tmp_path: Path,
) -> None:
    root = make_project(tmp_path, "", settings="continues = false\n")
    stale = add_run(root, "stale", ended=None, exit_code=None, pid=os.getpid())
    write(stale / "run.lock", "")

    run(root)

    recorded = folders(root)
    assert len(recorded) == 2
    assert recorded[stale]["ended_by"] == "lost"
    assert [r["exit_code"] for folder, r in recorded.items() if folder != stale] == [0]


@pytest.mark.parametrize(
    ("settings", "fields"),
    [
        ("continues = true\n", {"excluded": True}),
        (
            "continues = true\ncounts = \"exit_code = 0 AND created > '2026-10-18'\"\n",
            {"exit_code": 0},
        ),
    ],
    ids=["excluded", "not-counting"],
)
def test_runs_that_did_not_end_badly_get_a_new_folder(
    tmp_path: Path, settings: str, fields: dict[str, object]
) -> None:
    root = make_project(tmp_path, "", settings=settings)
    old = add_run(root, "old", **fields)

    run(root)

    recorded = folders(root)
    assert len(recorded) == 2
    assert "invocations" not in recorded[old]
    assert (old / "state.txt").read_text() == "x"


def test_without_continues_a_failed_run_is_redone_in_a_new_folder(
    tmp_path: Path,
) -> None:
    root = make_project(tmp_path, "1", settings="continues = false\n")

    run(root)
    run(root)

    recorded = folders(root)
    assert sorted(r["exit_code"] for r in recorded.values()) == [0, 1]
    for folder, record in recorded.items():
        assert "invocations" not in record
        assert (folder / "state.txt").read_text() == "x"
        assert (folder / "stdout.log").read_text() == "launch 1\n"
        assert (folder / "run.lock").exists()
