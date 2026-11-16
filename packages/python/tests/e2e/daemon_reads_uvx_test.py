import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import psutil

RUN = "20261114-000001-quiet-pond"
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + bytes(range(256))


def inotify_watches(pid: int) -> int:
    watches = 0
    for process in [psutil.Process(pid), *psutil.Process(pid).children(True)]:
        for fd in os.listdir(f"/proc/{process.pid}/fd"):
            try:
                if os.readlink(f"/proc/{process.pid}/fd/{fd}") != "anon_inode:inotify":
                    continue
                info = Path(f"/proc/{process.pid}/fdinfo/{fd}").read_text()
            except FileNotFoundError:
                continue
            watches += sum(line.startswith("inotify wd:") for line in info.splitlines())
    return watches


def events(text: str) -> list[tuple[str, str, object]]:
    found = []
    for block in text.split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if line)
        if fields:
            found.append((fields["event"], fields["id"], json.loads(fields["data"])))
    return found


class Curl:
    """One curl reading a read route until it is closed."""

    def __init__(self, path: Path, route: str, *headers: str) -> None:
        self.process = subprocess.Popen(
            ["curl", "-sS", "-N", "--unix-socket", str(path)]
            + [arg for header in headers for arg in ("-H", header)]
            + [f"http://labnotes{route}"],
            stdout=subprocess.PIPE,
            text=True,
        )

    def close(self) -> list[tuple[str, str, object]]:
        time.sleep(1)
        self.process.terminate()
        out, _ = self.process.communicate(timeout=10)
        return events(out)


def test_installed_daemon_serves_runs_files_and_tails_to_curl(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    assert shutil.which("curl"), "curl is needed to prove plain HTTP"
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text('continues = false\ncommand = "true"\n')
    for name in ("a", "b", "c"):
        (root / f"data/{name}/deep/more").mkdir(parents=True)
    folder = root / "exp/runs" / RUN
    folder.mkdir(parents=True)
    (folder / "run.json").write_text(
        json.dumps({"params": {}, "created": "2026-11-14T00:00:01Z"})
    )
    (folder / "stdout.log").write_text("out one\n")
    (folder / "image.png").write_bytes(PNG)
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

            runs = Curl(path, "/runs")
            files = Curl(path, f"/runs/{RUN}/files")
            tail = Curl(path, f"/runs/{RUN}/files/stdout.log")
            image = Curl(path, f"/runs/{RUN}/files/image.png")
            time.sleep(2)
            watches = inotify_watches(daemon.pid)
            assert watches == 1 + sum(
                1 for found in (root / "exp").rglob("*") if found.is_dir()
            )
            with (folder / "stdout.log").open("a") as out:
                out.write("out two\n")

            [(name, seen, state), *changes] = runs.close()
            assert name == "state"
            assert [
                (run["id"], run["name"], run["status"])
                for run in state  # type: ignore[attr-defined]
            ] == [(RUN, "quiet-pond", "running")]
            assert changes[-1][0] == "run"
            assert changes[-1][2]["size"] == sum(  # type: ignore[index]
                found.stat().st_size for found in folder.iterdir()
            )

            [(name, _, listed), *_] = files.close()
            assert name == "state"
            assert sorted(file["name"] for file in listed) == [  # type: ignore[attr-defined]
                "image.png",
                "run.json",
                "stdout.log",
            ]

            assert tail.close() == [
                ("state", "8", {"name": "stdout.log", "size": 8, "text": "out one\n"}),
                ("append", "16", {"text": "out two\n"}),
            ]
            assert image.close() == [
                (
                    "state",
                    str(len(PNG)),
                    {"name": "image.png", "size": len(PNG), "type": "image/png"},
                )
            ]

            with (folder / "stdout.log").open("a") as out:
                out.write("out three\n")
            resumed = Curl(
                path, f"/runs/{RUN}/files/stdout.log", "Last-Event-ID: 16"
            ).close()
            assert resumed == [("append", "26", {"text": "out three\n"})]

            again = Curl(path, "/runs", f"Last-Event-ID: {seen}").close()
            assert again[0][0] == "state"
            assert inotify_watches(daemon.pid) == watches
        finally:
            daemon.terminate()
            daemon.wait(timeout=30)
