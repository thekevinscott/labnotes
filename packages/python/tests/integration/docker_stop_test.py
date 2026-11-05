import asyncio
import os
from pathlib import Path

import pytest

from labnotes.runner.execute_run import execute_run
from labnotes.runner.signal_tree import signal_tree


def test_timeout_kills_the_labeled_container(
    tmp_path: Path, fake_docker: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for key, value in fake_docker.items():
        monkeypatch.setenv(key, value)
    folder = tmp_path / "run"
    folder.mkdir()
    state = Path(fake_docker["FAKE_DOCKER_STATE"])
    running: set[asyncio.subprocess.Process] = set()
    tree = set()

    def stop() -> None:
        for process in running:
            signal_tree(process.pid, 15, tree)

    async def go() -> dict[str, object]:
        return await execute_run(
            tmp_path,
            folder,
            "docker run --rm --label labnotes.run=$LABNOTES_RUN alpine sleep 30",
            {},
            running,
            asyncio.Event(),
            tree,
            timeout=0.5,
            stop=stop,
            state_file=tmp_path / "state.json",
            memory_interval=0,
            environment={**os.environ, **fake_docker},
        )

    result = asyncio.run(go())
    assert result["ended_by"] == "timeout"
    assert not state.exists(), "timed-out Docker client left its container running"
