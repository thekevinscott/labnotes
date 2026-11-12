import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import psutil
import httpx2
import pytest
from curtaincall import expect

from conftest import Tui


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        yield Path(folder)


def run_state() -> Path:
    return Path(os.environ["XDG_STATE_HOME"]) / "labnotes" / "run-state"


def run_state_files() -> list[str]:
    return sorted(
        str(path.relative_to(run_state()))
        for path in run_state().rglob("*")
        if path.is_file()
    )


def daemons(root: Path) -> list[psutil.Process]:
    config = str(root / ".labnotes.toml")
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (cmdline := process.info["cmdline"] or []) and "daemon" in cmdline
    ]


def wait_until(check, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while not check():
        assert time.monotonic() < deadline, "condition did not hold in time"
        time.sleep(0.05)


def test_uvx_runs_write_no_journals_and_leave_run_state_as_it_was(
    tmp_path: Path, tui: Tui, runtime: Path
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    seen = []
    for repeats in (2, 4):
        (root / "exp/experiment.toml").write_text(
            f'continues = false\ncommand = "{sys.executable} -c pass"\n'
            f"repeats = {repeats}\n"
        )
        term = tui(
            root, "experiments", "exp", "run", env={"XDG_RUNTIME_DIR": str(runtime)}
        )
        expect(term.get_by_text("2 passed, 0 failed.")).to_be_visible(timeout=120)
        tui.quit(term)
        wait_until(lambda: not daemons(root))
        seen.append(run_state_files())

    assert len(list(root.glob("exp/runs/*/run.json"))) == 4
    assert [name for name in seen[0] if name.endswith(".jsonl")] == []
    assert seen[1] == seen[0]


def test_uvx_attach_finds_the_live_batch_by_the_daemons_own_id(
    tmp_path: Path, tui: Tui, runtime: Path
) -> None:
    root = tmp_path / "project"
    release = tmp_path / "release"
    hold = tmp_path / "hold.py"
    hold.write_text(
        "import pathlib, time\n"
        "print('working', flush=True)\n"
        f"while not pathlib.Path({str(release)!r}).exists():\n"
        "    time.sleep(0.1)\n"
    )
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = '{sys.executable} {hold}'\n"
    )
    env = {"XDG_RUNTIME_DIR": str(runtime)}
    try:
        first = tui(root, "experiments", "exp", "run", env=env)
        expect(first.get_by_text("working")).to_be_visible(timeout=120)
        [path] = runtime.glob("labnotes/*.sock")
        with httpx2.Client(
            transport=httpx2.HTTPTransport(uds=str(path)),
            base_url="http://labnotes",
            timeout=30,
        ) as client:
            reply = client.get("/batches").json()
        assert reply["ok"] is True, reply
        [batch] = reply["batches"]
        assert "/" not in batch and not batch.endswith(".jsonl")

        second = tui(root, "experiments", "exp", "attach", env=env)
        expect(second.get_by_text("working")).to_be_visible(timeout=120)
        release.touch()
        for term in (first, second):
            expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=30)
            tui.quit(term)
    finally:
        release.touch()
    assert [p for p in run_state().rglob("*.jsonl")] == []
