import json
import shlex
import os
import sys
import time
from pathlib import Path

from curtaincall import Terminal, expect


def test_running_invocation_can_be_reconstructed_from_disk(tmp_path: Path) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text(
        "continues = false\n"
        f"command = \"{sys.executable} -c 'import time; time.sleep(2)'\"\n"
        "repeats = 2\nconcurrency = 1\n"
    )
    term = Terminal(
        shlex.join(
            [
                str(Path(sys.executable).parent / "labnotes"),
                "-c",
                str(tmp_path / ".labnotes.toml"),
                "experiments",
                "exp",
                "run",
            ]
        ),
        rows=30,
        cols=120,
    )
    term.start()
    state_dir = Path(os.environ["XDG_STATE_HOME"]) / "labnotes" / "run-state"
    state = None
    try:
        events = []
        for _ in range(80):
            journals = list(state_dir.glob("*/*.jsonl"))
            if journals:
                state = journals[0]
                events = [json.loads(line) for line in state.read_text().splitlines()]
                if any(e["event"] == "started" for e in events):
                    break
            time.sleep(0.05)
        assert events and events[0]["event"] == "planned"
        planned = events[0]
        assert len(planned["runs"]) == 2
        assert planned["concurrency"] == 1
        started = next(e for e in events if e["event"] == "started")
        assert started["at"] <= time.time()
        assert started["run"] in {r["run"] for r in planned["runs"]}
        expect(term.get_by_text("2 passed, 0 failed.")).to_be_visible(timeout=15)
        term.key_ctrl_c()
        assert term.wait(timeout=10) == 0
        assert state is not None
        finished = [json.loads(line) for line in state.read_text().splitlines()]
        assert len([e for e in finished if e["event"] == "ended"]) == 2
        assert finished[-1]["event"] == "idle"
    finally:
        term.kill()


def test_concurrent_invocations_keep_separate_journals(tmp_path: Path) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text(
        "continues = false\n"
        f"command = \"{sys.executable} -c 'import time; time.sleep(3)'\"\n"
        "repeats = 1\n[params]\nm = ['a', 'b']\n"
    )
    command = [
        str(Path(sys.executable).parent / "labnotes"),
        "-c",
        str(tmp_path / ".labnotes.toml"),
        "experiments",
        "exp",
        "run",
    ]
    processes = [
        Terminal(shlex.join([*command, f"--m={value}"]), rows=30, cols=120)
        for value in ("a", "b")
    ]
    for process in processes:
        process.start()
    try:
        journals = []
        for _ in range(100):
            journals = list(
                (Path(os.environ["XDG_STATE_HOME"]) / "labnotes/run-state").glob(
                    "*/*.jsonl"
                )
            )
            if len(journals) == 2 and all(
                "started" in path.read_text() for path in journals
            ):
                break
            time.sleep(0.05)
        assert len(journals) == 2
        plans = [
            [json.loads(line) for line in path.read_text().splitlines()][0]
            for path in journals
        ]
        assert sorted(plan["runs"][0]["params"]["m"] for plan in plans) == ["a", "b"]
        assert all(len(plan["runs"]) == 1 for plan in plans)

        mine = {
            plan["runs"][0]["params"]["m"]: plan["runs"][0]["run"] for plan in plans
        }
        for process, value in zip(processes, ("a", "b"), strict=True):
            other = mine["b" if value == "a" else "a"]
            expect(process.get_by_text(mine[value])).to_be_visible(timeout=15)
            expect(process.get_by_text(other)).not_to_be_visible()

        for process in processes:
            expect(process.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=15)
            process.key_ctrl_c()
            assert process.wait(timeout=10) == 0
        for path in journals:
            events = [json.loads(line) for line in path.read_text().splitlines()]
            assert len([event for event in events if event["event"] == "started"]) == 1
            assert len([event for event in events if event["event"] == "ended"]) == 1
    finally:
        for process in processes:
            process.kill()
