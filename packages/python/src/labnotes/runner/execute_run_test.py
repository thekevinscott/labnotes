import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.execute_run import execute_run

PARAMS: dict[str, object] = {"m": "a b"}


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    process = mock.Mock(pid=42)
    process.wait = mock.AsyncMock(return_value=3)
    with (
        mock.patch(
            "labnotes.runner.execute_run.shell_command", return_value="study"
        ) as shell_command,
        mock.patch("labnotes.runner.execute_run.write_run_json") as write_run_json,
        mock.patch(
            "labnotes.runner.execute_run.iso_time", side_effect=["start", "end"]
        ),
        mock.patch(
            "labnotes.runner.execute_run.asyncio.create_subprocess_shell",
            new=mock.AsyncMock(return_value=process),
        ) as spawn,
        mock.patch(
            "labnotes.runner.execute_run.wait_for_group", new=mock.AsyncMock()
        ) as wait_for_group,
    ):
        yield {
            "wait_for_group": wait_for_group,
            "shell_command": shell_command,
            "write_run_json": write_run_json,
            "spawn": spawn,
            "process": process,
        }


def run(tmp_path: Path, running: set[object] | None = None) -> dict[str, object]:
    return asyncio.run(
        execute_run(
            tmp_path / "root",
            tmp_path,
            "uv run x.py",
            PARAMS,
            set() if running is None else running,  # type: ignore[arg-type]
        )
    )


def test_runs_the_command_from_the_root(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    run(tmp_path)

    collaborators["shell_command"].assert_called_once_with(
        "uv run x.py", tmp_path, PARAMS
    )
    spawn = collaborators["spawn"]
    assert spawn.await_args.args == ("study",)
    kwargs = spawn.await_args.kwargs
    assert (kwargs["cwd"], kwargs["start_new_session"]) == (tmp_path / "root", True)
    assert kwargs["stdout"].name == str(tmp_path / "stdout.log")
    assert kwargs["stderr"].name == str(tmp_path / "stderr.log")


def test_records_the_run_before_and_after(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    snapshots: list[dict[str, object]] = []
    collaborators["write_run_json"].side_effect = lambda _, run: snapshots.append(
        dict(run)
    )

    result = run(tmp_path)

    started = {
        "params": PARAMS,
        "created": "start",
        "ended": None,
        "exit_code": None,
        "error": None,
    }
    assert snapshots == [started, {**started, "ended": "end", "exit_code": 3}]
    assert result == snapshots[-1]
    assert collaborators["write_run_json"].call_args.args[0] == tmp_path


def test_tracks_the_process_while_it_runs(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    running: set[object] = set()
    seen: list[bool] = []

    async def wait() -> int:
        seen.append(collaborators["process"] in running)
        return 0

    async def wait_for_group(group: int) -> None:
        seen.append(collaborators["process"] in running and group == 42)

    collaborators["process"].wait = wait
    collaborators["wait_for_group"].side_effect = wait_for_group

    run(tmp_path, running)

    assert seen == [True, True]
    assert running == set()


def test_records_a_command_that_cannot_start(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["spawn"].side_effect = OSError("no shell")

    result = run(tmp_path)

    assert (result["exit_code"], result["error"], result["ended"]) == (
        None,
        "no shell",
        "end",
    )
