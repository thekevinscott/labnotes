import asyncio
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from labnotes.models import Controls
from labnotes.read_config import read_config
from labnotes.runner.prepare_experiment import prepare_experiment
from labnotes.runner.run_experiment import run_experiment

WAIT = """
import sys, time
from pathlib import Path

Path(sys.argv[1]).touch()
while not Path(sys.argv[2]).exists():
    time.sleep(0.05)
"""


@pytest.fixture(autouse=True)
def release_waiters(tmp_path: Path) -> Iterator[None]:
    yield
    for name in ("set-up", "release"):
        (tmp_path / name).touch()


def make_project(root: Path, setup: bool) -> Path:
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "wait.py").write_text(WAIT)
    wait = f"{sys.executable} {root / 'wait.py'}"
    hook = f"setup = '''{wait} {root / 'setting-up'} {root / 'set-up'}'''\n"
    (root / "exp" / "experiment.toml").write_text(
        f"continues = false\nrepeats = 3\n"
        f"command = '''{wait} {root / 'running'} {root / 'release'}'''\n"
        + (hook if setup else "")
    )
    return root


async def until(check: object, seconds: float = 20) -> None:
    async with asyncio.timeout(seconds):
        while not check():  # type: ignore[operator]
            await asyncio.sleep(0.05)


def started(events: list[dict[str, object]]) -> int:
    return sum(event["event"] == "started" for event in events)


def peak(events: list[dict[str, object]]) -> int:
    live = top = 0
    for event in events:
        live += {"started": 1, "ended": -1}.get(str(event["event"]), 0)
        top = max(top, live)
    return top


async def launch(
    root: Path, concurrency: int, events: list[dict[str, object]]
) -> tuple[asyncio.Task[list[dict[str, object]]], Controls]:
    config = read_config(root / ".labnotes.toml")
    experiment, _ = await prepare_experiment(config, "exp", None, concurrency)
    heard: list[Controls] = []

    def listen(controls: Controls) -> None:
        heard.append(controls)
        controls.finish()

    task = asyncio.create_task(
        run_experiment(config, "exp", experiment, concurrency, events.append, listen)
    )
    await until(lambda: heard)
    return task, heard[0]


@pytest.mark.parametrize(("concurrency", "to"), [(1, 3), (2, 1)])
def test_a_concurrency_change_during_setup_waits_for_setup_to_end(
    tmp_path: Path, concurrency: int, to: int
) -> None:
    root = make_project(tmp_path, setup=True)
    events: list[dict[str, object]] = []

    async def go() -> None:
        task, controls = await launch(root, concurrency, events)
        await until((root / "setting-up").exists)
        controls.set_concurrency(to)
        await asyncio.sleep(1)
        assert started(events) == 0
        assert not (root / "running").exists()
        changes = [event for event in events if event["event"] == "concurrency"]
        assert len(changes) == 1
        assert changes[0]["concurrency"] == to
        assert isinstance(changes[0]["at"], float)
        (root / "set-up").touch()
        await until(lambda: started(events) == to)
        await asyncio.sleep(0.5)
        assert started(events) == to
        (root / "release").touch()
        await asyncio.wait_for(task, 30)

    asyncio.run(go())

    assert started(events) == 3
    assert peak(events) == to


def test_a_concurrency_change_without_setup_starts_runs_at_once(
    tmp_path: Path,
) -> None:
    root = make_project(tmp_path, setup=False)
    events: list[dict[str, object]] = []

    async def go() -> None:
        task, controls = await launch(root, 1, events)
        await until((root / "running").exists)
        controls.set_concurrency(3)
        await until(lambda: started(events) == 3)
        assert not (root / "release").exists()
        (root / "release").touch()
        await asyncio.wait_for(task, 30)

    asyncio.run(go())

    assert peak(events) == 3
