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
            "labnotes.runner.execute_run.wait_for_tree", new=mock.AsyncMock()
        ) as wait_for_tree,
    ):
        yield {
            "wait_for_tree": wait_for_tree,
            "shell_command": shell_command,
            "write_run_json": write_run_json,
            "spawn": spawn,
            "process": process,
        }


TREE: set[object] = {"orphan"}


def run(
    tmp_path: Path, running: set[object] | None = None, stopping: bool = False
) -> dict[str, object]:
    async def go() -> dict[str, object]:
        event = asyncio.Event()
        if stopping:
            event.set()
        return await execute_run(
            tmp_path / "root",
            tmp_path,
            "uv run x.py",
            PARAMS,
            set() if running is None else running,  # type: ignore[arg-type]
            event,
            TREE,  # type: ignore[arg-type]
        )

    return asyncio.run(go())


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
    assert kwargs["cwd"] == tmp_path / "root"
    assert "start_new_session" not in kwargs
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

    async def wait_for_tree(tree: set[object]) -> None:
        seen.append(collaborators["process"] in running and tree is TREE)

    collaborators["process"].wait = wait
    collaborators["wait_for_tree"].side_effect = wait_for_tree

    run(tmp_path, running, stopping=True)

    assert seen == [True, True]
    assert running == set()


def test_ends_a_normal_exit_without_waiting_for_leftovers(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    result = run(tmp_path)

    collaborators["wait_for_tree"].assert_not_awaited()
    assert result["exit_code"] == 3


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


def test_forces_color_in_the_child(
    tmp_path: Path,
    collaborators: dict[str, mock.MagicMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
    monkeypatch.setenv("KEPT", "1")

    run(tmp_path)

    env = collaborators["spawn"].await_args.kwargs["env"]
    assert env["FORCE_COLOR"] == "1"
    assert env["CLICOLOR_FORCE"] == "1"
    assert env["KEPT"] == "1"


def test_points_the_child_at_its_run_log(
    tmp_path: Path,
    collaborators: dict[str, mock.MagicMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LABNOTES_LOG", "/parent/log.jsonl")

    run(tmp_path)

    env = collaborators["spawn"].await_args.kwargs["env"]
    assert env["LABNOTES_LOG"] == str(tmp_path / "log.jsonl")


def test_keeps_color_settings_the_user_chose(
    tmp_path: Path,
    collaborators: dict[str, mock.MagicMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FORCE_COLOR", "0")
    monkeypatch.setenv("CLICOLOR_FORCE", "0")

    run(tmp_path)

    env = collaborators["spawn"].await_args.kwargs["env"]
    assert env["FORCE_COLOR"] == "0"
    assert env["CLICOLOR_FORCE"] == "0"
