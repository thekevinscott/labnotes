import asyncio
from pathlib import Path

import pytest

from labnotes.runner.invocation_hook import invocation_hook


def test_runs_the_command_from_the_root(tmp_path: Path) -> None:
    asyncio.run(invocation_hook(tmp_path, "setup", "touch made"))

    assert (tmp_path / "made").exists()


def test_fails_with_the_exit_code_and_stderr(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as error:
        asyncio.run(invocation_hook(tmp_path, "setup", "echo broke >&2; exit 3"))

    assert str(error.value) == "setup command echo broke >&2; exit 3 exited 3: broke"


def test_fails_without_detail_when_stderr_is_empty(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as error:
        asyncio.run(invocation_hook(tmp_path, "teardown", "exit 1"))

    assert str(error.value) == "teardown command exit 1 exited 1"


def test_fails_when_a_signal_ends_the_command(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as error:
        asyncio.run(invocation_hook(tmp_path, "setup", "kill -9 $$"))

    assert str(error.value) == "setup command kill -9 $$ exited -9"
