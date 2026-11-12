import asyncio
import json
import sys
from pathlib import Path

import pytest

from labnotes.runner.is_retryable import is_retryable

ECHO = f"{sys.executable} -c 'import sys; d = sys.stdin.read(); print(d); sys.exit(int(open(\"code\").read()))'"


@pytest.mark.parametrize(("code", "expected"), [(0, True), (1, False), (75, False)])
def test_retries_only_when_the_command_exits_0(
    tmp_path: Path, code: int, expected: bool
) -> None:
    (tmp_path / "code").write_text(str(code))

    assert (
        asyncio.run(is_retryable(ECHO, tmp_path, {}, tmp_path / "log", {}, set()))
        is expected
    )


def test_sends_the_attempt_as_json_on_stdin_and_logs_the_output(
    tmp_path: Path,
) -> None:
    (tmp_path / "code").write_text("0")
    attempt = {"exit_code": 1, "run": "r"}

    asyncio.run(is_retryable(ECHO, tmp_path, attempt, tmp_path / "log", {}, set()))

    assert json.loads((tmp_path / "log").read_text()) == attempt


def test_gives_up_when_the_command_cannot_start(tmp_path: Path) -> None:
    assert not asyncio.run(
        is_retryable("x", tmp_path / "missing", {}, tmp_path / "log", {}, set())
    )


def test_gives_up_when_the_command_dies(tmp_path: Path) -> None:
    command = "kill -9 $$"

    assert not asyncio.run(
        is_retryable(command, tmp_path, {}, tmp_path / "log", {}, set())
    )


def test_lists_the_command_as_running_until_it_exits(tmp_path: Path) -> None:
    running: set[asyncio.subprocess.Process] = set()
    seen: list[int] = []

    async def check() -> bool:
        task = asyncio.create_task(
            is_retryable("sleep 0.2", tmp_path, {}, tmp_path / "log", {}, running)
        )
        await asyncio.sleep(0.1)
        seen.append(len(running))
        return await task

    assert asyncio.run(check())
    assert (seen, running) == ([1], set())
