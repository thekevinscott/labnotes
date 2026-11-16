import json
import os
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

UNFINISHED = {
    "params": {},
    "created": "2026-10-17T00:00:00Z",
    "ended": None,
    "exit_code": None,
    "error": None,
}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


def test_installed_daemon_start_finalizes_only_its_experiments_lost_runs(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    write(root / ".labnotes.toml", "")
    write(root / "exp/experiment.toml", "continues = false\ncommand = 'true'\n")
    write(root / "other/experiment.toml", "continues = false\ncommand = 'true'\n")
    write(root / "exp/runs/lost/run.json", json.dumps(UNFINISHED))
    write(root / "other/runs/lost/run.json", json.dumps(UNFINISHED))
    with TemporaryDirectory(prefix="ln-runtime-") as runtime:
        env = {**os.environ, **uvx, "XDG_RUNTIME_DIR": runtime}
        daemon = subprocess.Popen(
            ["uvx", "labnotes", "-c", str(root / ".labnotes.toml"), "daemon", "exp"],
            cwd=root,
            env=env,
            stdout=subprocess.DEVNULL,
        )
        try:
            for _ in range(600):
                sockets = list(Path(runtime).glob("labnotes/*.sock"))
                if sockets:
                    break
                time.sleep(0.1)
            [path] = sockets
            started = subprocess.run(
                ["curl", "-sS", "-N", "--unix-socket", str(path)]
                + ["-X", "POST", "-d", "{}", "http://labnotes/start"],
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            ).stdout
            assert '"ok": true' in started.strip().split("\n\n")[-1]
        finally:
            daemon.terminate()
            daemon.wait(timeout=30)

    assert read(root / "exp/runs/lost/run.json")["ended_by"] == "lost"
    assert read(root / "other/runs/lost/run.json") == UNFINISHED
