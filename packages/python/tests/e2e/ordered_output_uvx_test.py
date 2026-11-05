import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

INTERLEAVE = """
import sys, time
for i in range(4):
    print(f"out {i}", flush=True)
    time.sleep(0.05)
    print(f"err {i}", file=sys.stderr, flush=True)
    time.sleep(0.05)
"""


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def streamed_output(url: str) -> list[tuple[str, str]]:
    for _ in range(200):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                body = response.read().decode()
            break
        except OSError:
            time.sleep(0.1)
    else:
        raise AssertionError(f"server never answered {url}")
    messages = [
        json.loads(block.removeprefix("data: "))
        for block in body.split("\n\n")
        if block.startswith("data: ")
    ]
    return [
        (message["stream"], line)
        for message in messages
        for line in message["text"].splitlines()
    ]


def test_uvx_run_output_reads_back_in_write_order(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "interleave.py").write_text(INTERLEAVE)
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} interleave.py"\n'
    )
    env = {**os.environ, **uvx}
    labnotes = ["uvx", "labnotes", "-c", str(root / ".labnotes.toml")]

    subprocess.run(
        [*labnotes, "experiments", "exp", "run", "--headless"],
        cwd=root,
        env=env,
        check=True,
        timeout=120,
    )

    [record] = root.glob("exp/runs/*/run.json")
    run_id = record.parent.name
    assert json.loads(record.read_text())["output"] == "output.jsonl"
    port = free_port()
    server = subprocess.Popen(
        [*labnotes, "server", "-p", str(port)],
        cwd=root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        lines = streamed_output(
            f"http://127.0.0.1:{port}/experiments/exp/output/{run_id}"
        )
    finally:
        server.terminate()
        server.wait(timeout=20)

    assert lines == [
        (stream, f"{name} {i}")
        for i in range(4)
        for stream, name in (("stdout", "out"), ("stderr", "err"))
    ]
