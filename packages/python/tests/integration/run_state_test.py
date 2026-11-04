import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

from labnotes.runner.run_state import RunState
from labnotes.runner.start_experiment import ExperimentStart
from labnotes.tui.run_app import RunApp


def test_running_invocation_can_be_reconstructed_from_disk(tmp_path: Path) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text(
        "continues = false\n"
        f"command = \"{sys.executable} -c 'import time; time.sleep(2)'\"\n"
        "repeats = 2\nconcurrency = 1\n"
    )
    process = subprocess.Popen(
        [
            str(Path(sys.executable).parent / "labnotes"),
            "-c",
            str(tmp_path / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
        ],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
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
        assert process.wait(timeout=15) == 0
        assert state is not None
        finished = [json.loads(line) for line in state.read_text().splitlines()]
        assert len([e for e in finished if e["event"] == "ended"]) == 2
        assert finished[-1]["event"] == "idle"
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()


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
        subprocess.Popen(
            [*command, f"--m={value}"],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for value in ("a", "b")
    ]
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

        async def shown_ids(path: Path) -> set[str]:
            async def attach(report, listen):
                report({"event": "wake up"})
                await asyncio.Event().wait()
                return []

            config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
            app = RunApp(
                ExperimentStart(RunState(path), attach),
                "exp",
                ("run", "params", "status", "time"),
                config,
            )
            async with app.run_test() as pilot:
                await pilot.pause()
                return set(app.body.cells)

        for path, plan in zip(journals, plans, strict=True):
            assert asyncio.run(shown_ids(path)) == {plan["runs"][0]["run"]}

        assert all(process.wait(timeout=10) == 0 for process in processes)
        for path in journals:
            events = [json.loads(line) for line in path.read_text().splitlines()]
            assert len([event for event in events if event["event"] == "started"]) == 1
            assert len([event for event in events if event["event"] == "ended"]) == 1
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait()
