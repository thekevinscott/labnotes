import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any
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
        mock.patch("labnotes.runner.execute_run.psutil") as psutil,
        mock.patch(
            "labnotes.runner.execute_run.record_memory", new=mock.AsyncMock()
        ) as record_memory,
    ):
        psutil.Error = Gone
        psutil.Process.return_value.create_time.return_value = 1234.5
        yield {
            "wait_for_tree": wait_for_tree,
            "shell_command": shell_command,
            "write_run_json": write_run_json,
            "spawn": spawn,
            "process": process,
            "psutil": psutil,
            "record_memory": record_memory,
        }


class Gone(Exception):
    pass


TREE: set[object] = {"orphan"}


def run(
    tmp_path: Path,
    running: set[object] | None = None,
    stopping: bool = False,
    timeout: float | None = None,
    stop: mock.Mock | None = None,
    stopped: bool = False,
    memory_interval: float = 0,
    **options: Any,
) -> dict[str, object]:
    if stopped:
        options["stopped"] = lambda: True

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
            timeout=timeout,
            stop=mock.Mock() if stop is None else stop,
            state_file=tmp_path / "state.json",
            memory_interval=memory_interval,
            **options,
        )

    return asyncio.run(go())


def test_runs_the_command_from_the_root(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    run(tmp_path)

    collaborators["shell_command"].assert_called_once_with(
        "uv run x.py", tmp_path, PARAMS, ()
    )
    spawn = collaborators["spawn"]
    assert spawn.await_args.args == ("study",)
    kwargs = spawn.await_args.kwargs
    assert kwargs["cwd"] == tmp_path / "root"
    assert "start_new_session" not in kwargs
    assert kwargs["stdout"].name == str(tmp_path / "stdout.log")
    assert kwargs["stderr"].name == str(tmp_path / "stderr.log")


def test_appends_and_records_the_args(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    result = run(tmp_path, args=("--auth", "api"))

    collaborators["shell_command"].assert_called_once_with(
        "uv run x.py", tmp_path, PARAMS, ("--auth", "api")
    )
    assert result["args"] == ["--auth", "api"]


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
        "command": "study",
        "created": "start",
        "ended": None,
        "exit_code": None,
        "error": None,
        "ended_by": None,
        "signal": None,
    }
    spawned = {**started, "pid": 42, "pid_created": 1234.5}
    assert snapshots == [started, spawned, {**spawned, "ended": "end", "exit_code": 3}]
    assert result == snapshots[-1]
    assert collaborators["write_run_json"].call_args.args[0] == tmp_path
    collaborators["psutil"].Process.assert_called_once_with(42)


def test_records_the_pid_alone_when_the_process_is_already_gone(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["psutil"].Process.side_effect = Gone()

    result = run(tmp_path)

    assert result["pid"] == 42
    assert "pid_created" not in result


def test_records_which_run_a_retry_retries(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    snapshots: list[dict[str, object]] = []
    collaborators["write_run_json"].side_effect = lambda _, run: snapshots.append(
        dict(run)
    )

    result = run(tmp_path, retry_of="r1")

    assert [snapshot["retry_of"] for snapshot in snapshots] == ["r1", "r1", "r1"]
    assert result["retry_of"] == "r1"


def test_records_the_invocation_meta_from_the_first_write(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    snapshots: list[dict[str, object]] = []
    collaborators["write_run_json"].side_effect = lambda _, run: snapshots.append(
        dict(run)
    )
    meta = {"commit": "abc"}

    result = run(tmp_path, meta=meta)  # type: ignore[arg-type]

    assert [snapshot["meta"] for snapshot in snapshots] == [meta, meta, meta]
    assert result["meta"] == meta


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


def test_gives_the_child_its_own_run_id(
    tmp_path: Path,
    collaborators: dict[str, mock.MagicMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LABNOTES_RUN", "parent-run")

    run(tmp_path)

    env = collaborators["spawn"].await_args.kwargs["env"]
    assert env["LABNOTES_RUN"] == str(tmp_path.resolve())


@pytest.mark.parametrize("explicit_environment", [False, True])
def test_replaces_inherited_state_with_read_only_invocation_state(
    tmp_path: Path,
    collaborators: dict[str, mock.MagicMock],
    monkeypatch: pytest.MonkeyPatch,
    explicit_environment: bool,
) -> None:
    inherited = {
        "LABNOTES_STATE": "/parent/state.json",
        "LABNOTES_RUN_STATE": "/parent/run-state.json",
        "LABNOTES_OTHER": "parent",
    }
    for key, value in inherited.items():
        monkeypatch.setenv(key, value)

    run(tmp_path, environment=inherited if explicit_environment else None)

    env = collaborators["spawn"].await_args.kwargs["env"]
    assert [key for key in env if key in inherited] == ["LABNOTES_RUN_STATE"]
    assert env["LABNOTES_RUN_STATE"] == str(tmp_path / "state.json")


def test_uses_the_invocations_environment_and_preserves_its_own_run_vars(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    run(
        tmp_path,
        environment={
            "VALUE": "from-cli",
            "LABNOTES_LOG": "wrong",
            "LABNOTES_RUN": "wrong",
        },
    )

    env = collaborators["spawn"].await_args.kwargs["env"]
    assert env["VALUE"] == "from-cli"
    assert env["LABNOTES_LOG"] == str(tmp_path / "log.jsonl")
    assert env["LABNOTES_RUN"] == str(tmp_path.resolve())


def test_runs_with_the_same_folder_name_have_different_ids(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    first = tmp_path / "experiment-a" / "same"
    second = tmp_path / "experiment-b" / "same"
    first.mkdir(parents=True)
    second.mkdir(parents=True)

    with mock.patch(
        "labnotes.runner.execute_run.iso_time",
        side_effect=["start", "end", "start", "end"],
    ):
        run(first)
        first_id = collaborators["spawn"].await_args.kwargs["env"]["LABNOTES_RUN"]
        run(second)
        second_id = collaborators["spawn"].await_args.kwargs["env"]["LABNOTES_RUN"]

    assert first_id == str(first.resolve())
    assert second_id == str(second.resolve())
    assert first_id != second_id


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


def exits_after(process: mock.Mock, stop: mock.Mock, calls: int) -> None:
    exited = asyncio.Event()

    def stopped() -> None:
        if stop.call_count == calls:
            exited.set()

    async def wait() -> int:
        await exited.wait()
        return -15

    stop.side_effect = stopped
    process.wait = wait


def test_stops_a_run_that_outlasts_its_timeout(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    stop = mock.Mock()
    exits_after(collaborators["process"], stop, 1)

    result = run(tmp_path, timeout=0.01, stop=stop)

    stop.assert_called_once_with()
    assert (result["exit_code"], result["error"]) == (-15, "timed out after 0s")
    assert (result["ended_by"], result["signal"]) == ("timeout", 15)
    collaborators["wait_for_tree"].assert_awaited_once_with(TREE)


def test_kills_a_timed_out_run_after_the_grace(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    stop = mock.Mock()
    exits_after(collaborators["process"], stop, 2)

    with mock.patch("labnotes.runner.execute_run.GRACE_SECONDS", 0.01):
        result = run(tmp_path, timeout=0.01, stop=stop)

    assert stop.call_count == 2
    assert result["error"] == "timed out after 0s"


def test_cancels_the_kill_once_a_timed_out_run_ends(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    stop = mock.Mock()
    exits_after(collaborators["process"], stop, 1)

    async def go() -> None:
        with mock.patch("labnotes.runner.execute_run.GRACE_SECONDS", 0.05):
            await execute_run(
                tmp_path / "root",
                tmp_path,
                "uv run x.py",
                PARAMS,
                set(),
                asyncio.Event(),
                TREE,  # type: ignore[arg-type]
                timeout=0.01,
                stop=stop,
                state_file=tmp_path / "state.json",
                memory_interval=0,
            )
            await asyncio.sleep(0.1)

    asyncio.run(go())

    stop.assert_called_once_with()


def test_names_the_timeout_in_the_error(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    stop = mock.Mock()
    exits_after(collaborators["process"], stop, 1)

    with mock.patch(
        "labnotes.runner.execute_run.asyncio.wait",
        new=mock.AsyncMock(return_value=(set(), set())),
    ):
        result = run(tmp_path, timeout=1800, stop=stop)

    assert result["error"] == "timed out after 30m 00s"


def test_leaves_a_run_inside_its_timeout_alone(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    stop = mock.Mock()

    result = run(tmp_path, timeout=60, stop=stop)

    stop.assert_not_called()
    collaborators["wait_for_tree"].assert_not_awaited()
    assert (result["exit_code"], result["error"]) == (3, None)


def test_records_a_timeout_even_though_the_timeout_stopped_it(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    stop = mock.Mock()
    exits_after(collaborators["process"], stop, 1)

    result = run(tmp_path, timeout=0.01, stop=stop, stopped=True)

    assert result["ended_by"] == "timeout"


@pytest.mark.parametrize(("stopping", "stopped"), [(True, False), (False, True)])
def test_records_a_run_labnotes_stopped(
    tmp_path: Path,
    collaborators: dict[str, mock.MagicMock],
    stopping: bool,
    stopped: bool,
) -> None:
    collaborators["process"].wait = mock.AsyncMock(return_value=-15)

    result = run(tmp_path, stopping=stopping, stopped=stopped)

    assert (result["ended_by"], result["signal"]) == ("stop", 15)


def test_records_a_stopped_run_that_exits_on_its_own_terms(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["process"].wait = mock.AsyncMock(return_value=0)

    result = run(tmp_path, stopped=True)

    assert (result["exit_code"], result["ended_by"], result["signal"]) == (
        0,
        "stop",
        None,
    )


@pytest.mark.parametrize("exit_code", [137, -9])
def test_records_a_signal_labnotes_did_not_send(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock], exit_code: int
) -> None:
    collaborators["process"].wait = mock.AsyncMock(return_value=exit_code)

    result = run(tmp_path)

    assert (result["exit_code"], result["ended_by"], result["signal"]) == (
        exit_code,
        "signal",
        9,
    )


def test_records_no_cause_for_a_command_that_cannot_start(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["spawn"].side_effect = OSError("no shell")

    result = run(tmp_path, stopping=True)

    assert (result["ended_by"], result["signal"]) == (None, None)


@pytest.mark.parametrize("interval", [0, -1])
def test_records_no_memory_without_a_positive_interval(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock], interval: float
) -> None:
    run(tmp_path, memory_interval=interval)

    collaborators["record_memory"].assert_not_called()


def test_records_the_trees_memory_at_the_interval(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    run(tmp_path, memory_interval=0.5)

    collaborators["record_memory"].assert_awaited_once_with(
        tmp_path / "memory.jsonl", 42, 1234.5, 0.5
    )


def test_records_no_memory_without_the_process_start_time(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["psutil"].Process.side_effect = Gone()

    run(tmp_path, memory_interval=5)

    collaborators["record_memory"].assert_not_called()


def test_stops_recording_memory_when_the_run_ends(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    sampling: list[str] = []

    async def record(*_: object) -> None:
        sampling.append("started")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            sampling.append("stopped")
            raise

    async def exit_later() -> int:
        await asyncio.sleep(0)
        assert sampling == ["started"]
        return 0

    collaborators["record_memory"].side_effect = record
    collaborators["process"].wait = exit_later

    result = run(tmp_path, memory_interval=5)

    assert sampling == ["started", "stopped"]
    assert result["exit_code"] == 0
