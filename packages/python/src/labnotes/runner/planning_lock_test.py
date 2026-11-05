import asyncio
from pathlib import Path

import pytest

from labnotes.runner.planning_lock import planning_lock


def test_planning_lock_uses_project_state_across_temp_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    first_temp = tmp_path / "first-temp"
    second_temp = tmp_path / "second-temp"
    first_temp.mkdir()
    second_temp.mkdir()
    project = tmp_path / "project"
    project.mkdir()

    async def exercise() -> None:
        monkeypatch.setenv("TMPDIR", str(first_temp))
        async with planning_lock(project):
            locks = list((tmp_path / "state").rglob("plan.lock"))
            assert len(locks) == 1
            assert not (project / ".labnotes-plan.lock").exists()
        monkeypatch.setenv("TMPDIR", str(second_temp))
        async with planning_lock(project):
            assert list((tmp_path / "state").rglob("plan.lock")) == locks

    asyncio.run(exercise())


def test_cancelled_waiter_releases_its_file_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    async def exercise() -> None:
        async with planning_lock(tmp_path):
            entered = asyncio.Event()

            async def wait() -> None:
                entered.set()
                async with planning_lock(tmp_path):
                    raise AssertionError("cancelled waiter entered the lock")

            task = asyncio.create_task(wait())
            await entered.wait()
            await asyncio.sleep(0.1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        async with asyncio.timeout(1), planning_lock(tmp_path):
            pass

    asyncio.run(exercise())
