import json
import subprocess
import sys
import time
from pathlib import Path


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
    state = tmp_path / "exp" / "run-state.jsonl"
    try:
        events = []
        for _ in range(80):
            if state.exists():
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
        finished = [json.loads(line) for line in state.read_text().splitlines()]
        assert len([e for e in finished if e["event"] == "ended"]) == 2
        assert finished[-1]["event"] == "idle"
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
