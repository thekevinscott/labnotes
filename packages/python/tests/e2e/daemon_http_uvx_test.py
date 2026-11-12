import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory


def curl(path: Path, *args: str, codes: tuple[int, ...] = (0,)) -> str:
    result = subprocess.run(
        ["curl", "-sS", "--unix-socket", str(path), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode in codes, result.stderr
    return result.stdout


def test_installed_daemon_speaks_http_to_curl(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    assert shutil.which("curl"), "curl is needed to prove plain HTTP"
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    release = tmp_path / "release"
    hold = tmp_path / "hold.py"
    hold.write_text(
        "import pathlib, time\n"
        f"while not pathlib.Path({str(release)!r}).exists():\n"
        "    time.sleep(0.1)\n"
    )
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = '{sys.executable} {hold}'\n"
    )
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
            assert json.loads(curl(path, "http://labnotes/batches")) == {
                "ok": True,
                "batches": [],
            }
            started = curl(
                path, "-N", "-X", "POST", "-d", "{}", "http://labnotes/start"
            )
            assert "event: step\n" in started
            reply = started.strip().split("\n\n")[-1]
            assert reply.startswith("event: reply\ndata: ")
            batch = json.loads(reply.removeprefix("event: reply\ndata: "))["batch"]
            events = curl(path, "-N", "-m", "2", "http://labnotes/events", codes=(28,))
            assert events.startswith(
                f'event: batches\ndata: {{"batches": ["{batch}"]}}\n\n'
            )
            assert '"event": "planned"' in events
            assert json.loads(curl(path, "-X", "POST", "http://labnotes/stop")) == {
                "ok": True
            }
        finally:
            release.touch()
            daemon.terminate()
            daemon.wait(timeout=30)
