import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.runner.run_experiment import run_experiment

A: dict[str, object] = {"m": "a"}
B: dict[str, object] = {"m": "b"}
SIGKILL, SIGTERM = 9, 15


def experiment() -> mock.Mock:
    return mock.Mock(command="run", params={"m": ["a", "b"]}, repeats=2, counts="c")


@pytest.fixture
def collaborators(tmp_path: Path) -> Iterator[dict[str, mock.MagicMock]]:
    ids = iter(["r1", "r2", "r3"])
    with (
        mock.patch("labnotes.runner.run_experiment.open_tables") as open_tables,
        mock.patch(
            "labnotes.runner.run_experiment.list_experiment_runs",
            new=mock.AsyncMock(
                return_value=[
                    {"params": '{"m": "a"}', "counted": 1},
                    {"params": '{"m": "b"}', "counted": 0},
                ]
            ),
        ) as list_runs,
        mock.patch(
            "labnotes.runner.run_experiment.param_grid", return_value=[A, B]
        ) as param_grid,
        mock.patch(
            "labnotes.runner.run_experiment.plan_runs", return_value=[A, B]
        ) as plan_runs,
        mock.patch(
            "labnotes.runner.run_experiment.new_run_id",
            side_effect=lambda taken: next(ids),
        ) as new_run_id,
        mock.patch(
            "labnotes.runner.run_experiment.run_folder",
            side_effect=lambda root, template, name, run: root / name / run,
        ),
        mock.patch(
            "labnotes.runner.run_experiment.execute_run",
            new=mock.AsyncMock(return_value={"exit_code": 0, "error": None}),
        ) as execute_run,
        mock.patch(
            "labnotes.runner.run_experiment.signal",
            mock.Mock(SIGTERM=SIGTERM, SIGKILL=SIGKILL),
        ),
        mock.patch("labnotes.runner.run_experiment.os.killpg") as killpg,
        mock.patch(
            "labnotes.runner.run_experiment.new_invocation_id", return_value="inv1"
        ),
    ):
        yield {
            "open_tables": open_tables,
            "list_runs": list_runs,
            "param_grid": param_grid,
            "plan_runs": plan_runs,
            "new_run_id": new_run_id,
            "execute_run": execute_run,
            "killpg": killpg,
        }


def run(
    tmp_path: Path,
    report: mock.Mock,
    concurrency: int = 1,
    listen: mock.Mock | None = None,
) -> list[dict[str, object]]:
    config = mock.Mock(root=tmp_path, runs="{experiment}/{run}")
    hear = mock.Mock() if listen is None else listen

    def listening(controls: object) -> None:
        hear(controls)
        controls.finish()  # type: ignore[attr-defined]

    return asyncio.run(
        run_experiment(
            config,
            "exp",
            experiment(),
            concurrency,
            report,
            listening,
        )
    )


def test_plans_the_runs_still_needed(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    run(tmp_path, mock.Mock())

    collaborators["list_runs"].assert_awaited_once_with(
        collaborators["open_tables"].return_value, "exp", "c"
    )
    collaborators["param_grid"].assert_called_once_with({"m": ["a", "b"]})
    collaborators["plan_runs"].assert_called_once_with([A, B], 2, [A])


def test_runs_each_planned_run_in_a_new_folder(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    report = mock.Mock()

    results = run(tmp_path, report)

    assert results == [{"exit_code": 0, "error": None}] * 2
    calls = collaborators["execute_run"].await_args_list
    assert [c.args[:4] for c in calls] == [
        (tmp_path, tmp_path / "exp" / "r1", "run", A),
        (tmp_path, tmp_path / "exp" / "r2", "run", B),
    ]
    assert (tmp_path / "exp" / "r1").is_dir()
    assert [c.args[6] for c in calls] == ["inv1", "inv1"]
    ended = {"exit_code": 0, "error": None}
    assert [c.args[0] for c in report.call_args_list] == [
        {
            "event": "planned",
            "runs": [{"run": "r1", "params": A}, {"run": "r2", "params": B}],
            "concurrency": 1,
        },
        {"event": "started", "run": "r1", "params": A},
        {"event": "ended", "run": "r1", **ended},
        {"event": "started", "run": "r2", "params": B},
        {"event": "ended", "run": "r2", **ended},
        {"event": "idle"},
    ]


def test_checks_new_run_ids_against_existing_folders(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    (tmp_path / "exp" / "taken").mkdir(parents=True)

    run(tmp_path, mock.Mock())

    taken = collaborators["new_run_id"].call_args.args[0]
    assert (taken("taken"), taken("free")) == (True, False)


def test_names_every_run_before_the_first_starts(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    def started(taken: object) -> str:
        assert not collaborators["execute_run"].await_count
        return next(ids)

    ids = iter(["r1", "r2"])
    collaborators["new_run_id"].side_effect = started

    run(tmp_path, mock.Mock())

    taken = collaborators["new_run_id"].call_args.args[0]
    assert (taken("r1"), taken("r2")) == (True, True)


def test_runs_up_to_the_concurrency_at_once(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    live: list[int] = []
    peak = 0

    async def execute(*args: object) -> dict[str, object]:
        nonlocal peak
        live.append(1)
        peak = max(peak, len(live))
        await asyncio.sleep(0.01)
        live.pop()
        return {"exit_code": 0, "error": None}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, mock.Mock(), concurrency=2)

    assert peak == 2


def interrupting(times: int, listen: mock.Mock) -> object:
    async def execute(
        root: Path,
        folder: Path,
        command: str,
        params: object,
        running: set[object],
        stopping: asyncio.Event,
        invocation: str,
    ) -> dict[str, object]:
        running.add(mock.Mock(pid=42))
        assert not stopping.is_set()
        for _ in range(times):
            listen.call_args.args[0].interrupt()
        assert stopping.is_set()
        running.clear()
        return {"exit_code": -15, "error": None}

    return execute


def events(report: mock.Mock) -> list[object]:
    return [c.args[0]["event"] for c in report.call_args_list]


def test_first_interrupt_stops_runs_and_starts_no_more(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen = mock.Mock()
    collaborators["execute_run"].side_effect = interrupting(1, listen)
    report = mock.Mock()

    results = run(tmp_path, report, listen=listen)

    assert results == [{"exit_code": -15, "error": None}]
    collaborators["killpg"].assert_called_once_with(42, SIGTERM)
    assert events(report) == ["planned", "started", "stopping", "ended", "idle"]


def test_second_interrupt_kills_runs(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen = mock.Mock()
    collaborators["execute_run"].side_effect = interrupting(2, listen)
    report = mock.Mock()

    run(tmp_path, report, listen=listen)

    assert collaborators["killpg"].call_args_list == [
        mock.call(42, SIGTERM),
        mock.call(42, SIGKILL),
    ]
    assert events(report) == [
        "planned",
        "started",
        "stopping",
        "killing",
        "ended",
        "idle",
    ]


def test_a_late_interrupt_after_the_runs_end_does_nothing(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen = mock.Mock()
    collaborators["execute_run"].side_effect = interrupting(1, listen)
    report = mock.Mock()

    run(tmp_path, report, listen=listen)
    listen.call_args.args[0].interrupt()

    collaborators["killpg"].assert_called_once_with(42, SIGTERM)
    assert events(report) == ["planned", "started", "stopping", "ended", "idle"]


def test_ignores_a_run_that_already_exited(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen = mock.Mock()
    collaborators["execute_run"].side_effect = interrupting(1, listen)
    collaborators["killpg"].side_effect = ProcessLookupError

    run(tmp_path, mock.Mock(), listen=listen)


def test_moves_a_pending_run_to_the_front(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen = mock.Mock()
    report = mock.Mock()

    async def execute(*args: object) -> dict[str, object]:
        controls = listen.call_args.args[0]
        controls.run_next("r1")
        # Built at runtime, so an `is` comparison would miss it.
        controls.run_next("".join(["r", "4"]))
        return {"exit_code": 0, "error": None}

    ids = iter(["r1", "r2", "r3", "r4"])
    collaborators["new_run_id"].side_effect = lambda taken: next(ids)
    collaborators["plan_runs"].return_value = [A, B, A, B]
    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, listen=listen)

    reported = [c.args[0] for c in report.call_args_list]
    started = [e["run"] for e in reported if e["event"] == "started"]
    assert started == ["r1", "r4", "r2", "r3"]
    queued = {
        "event": "queued",
        "run": "r4",
        "pending": ["r4", "r2", "r3"],
        "held": [],
    }
    assert reported[2] == queued
    assert events(report).count("queued") == 1


def changing_concurrency(listen: mock.Mock, to: int, widths: list[int]) -> object:
    live = 0

    async def execute(*args: object) -> dict[str, object]:
        nonlocal live
        live += 1
        widths.append(live)
        if len(widths) == 1:
            listen.call_args.args[0].set_concurrency(to)
        await asyncio.sleep(0.01)
        live -= 1
        return {"exit_code": 0, "error": None}

    return execute


def reported(report: mock.Mock) -> list[dict[str, object]]:
    return [c.args[0] for c in report.call_args_list]


def test_raising_concurrency_starts_more_runs_at_once(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()
    widths: list[int] = []
    collaborators["plan_runs"].return_value = [A, B, A]
    collaborators["execute_run"].side_effect = changing_concurrency(listen, 3, widths)

    run(tmp_path, report, listen=listen)

    assert widths == [1, 2, 3]
    assert {"event": "concurrency", "concurrency": 3} in reported(report)


def test_lowering_concurrency_lets_running_runs_finish_first(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()
    widths: list[int] = []
    ids = iter(["r1", "r2", "r3", "r4"])
    collaborators["new_run_id"].side_effect = lambda taken: next(ids)
    collaborators["plan_runs"].return_value = [A, B, A, B]
    collaborators["execute_run"].side_effect = changing_concurrency(listen, 0, widths)

    results = run(tmp_path, report, concurrency=2, listen=listen)

    assert len(results) == 4
    assert widths == [1, 2, 1, 1]
    assert {"event": "concurrency", "concurrency": 1} in reported(report)


def test_a_failing_run_fails_the_experiment(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["execute_run"].side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        run(tmp_path, mock.Mock())


def planning(collaborators: dict[str, mock.MagicMock], count: int) -> None:
    ids = iter([f"r{n}" for n in range(1, count + 1)])
    collaborators["new_run_id"].side_effect = lambda taken: next(ids)
    collaborators["plan_runs"].return_value = [A, B] * (count // 2) + [A] * (count % 2)


def started_runs(report: mock.Mock) -> list[object]:
    return [e["run"] for e in reported(report) if e["event"] == "started"]


def test_a_deselected_run_does_not_run(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()
    planning(collaborators, 3)

    async def execute(root: Path, folder: Path, *args: object) -> dict[str, object]:
        if folder.name == "r1":
            listen.call_args.args[0].toggle("r2")
        return {"exit_code": 0, "error": None}

    collaborators["execute_run"].side_effect = execute

    results = run(tmp_path, report, listen=listen)

    assert len(results) == 2
    assert started_runs(report) == ["r1", "r3"]
    deselected = {"event": "deselected", "run": "r2", "pending": ["r3"], "held": ["r2"]}
    assert deselected in reported(report)


def test_a_reselected_run_goes_to_the_back_of_the_queue(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()
    planning(collaborators, 3)

    async def execute(*args: object) -> dict[str, object]:
        if len(started_runs(report)) == 1:
            controls = listen.call_args.args[0]
            controls.toggle("r2")
            controls.toggle("r2")
        return {"exit_code": 0, "error": None}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, listen=listen)

    assert started_runs(report) == ["r1", "r3", "r2"]
    reselected = {
        "event": "reselected",
        "run": "r2",
        "pending": ["r3", "r2"],
        "held": [],
    }
    assert reselected in reported(report)


def test_a_reselected_run_starts_at_once_when_there_is_room(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()
    planning(collaborators, 3)

    async def execute(root: Path, folder: Path, *args: object) -> dict[str, object]:
        if folder.name == "r1":
            controls = listen.call_args.args[0]
            controls.toggle("r3")
            await asyncio.sleep(0.01)
            controls.toggle("r3")
            await asyncio.sleep(0.01)
        return {"exit_code": 0, "error": None}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, concurrency=2, listen=listen)

    order = [(e["event"], e.get("run")) for e in reported(report)]
    assert order.index(("started", "r3")) < order.index(("ended", "r1"))


def test_toggling_a_run_that_is_not_waiting_does_nothing(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()

    async def execute(*args: object) -> dict[str, object]:
        listen.call_args.args[0].toggle("r1")
        return {"exit_code": 0, "error": None}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, listen=listen)

    assert events(report) == ["planned", "started", "ended", "started", "ended", "idle"]


def test_toggling_after_stopping_does_nothing(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()
    planning(collaborators, 3)

    async def execute(*args: object) -> dict[str, object]:
        controls = listen.call_args.args[0]
        controls.toggle("r2")
        controls.interrupt()
        controls.toggle("r2")
        return {"exit_code": -15, "error": None}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, listen=listen)

    assert started_runs(report) == ["r1"]
    assert events(report).count("reselected") == 0


def killing(listen: mock.Mock, *kills: tuple[str, str]) -> object:
    async def execute(
        root: Path,
        folder: Path,
        command: str,
        params: object,
        running: set[object],
        stopping: asyncio.Event,
        invocation: str,
    ) -> dict[str, object]:
        running.add(mock.Mock(pid=int(folder.name[1:])))
        for by, target in kills:
            if folder.name == by:
                listen.call_args.args[0].kill(target)
        await asyncio.sleep(0.01)
        running.clear()
        return {"exit_code": 0, "error": None}

    return execute


def test_kill_stops_only_that_run(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()
    planning(collaborators, 3)
    collaborators["execute_run"].side_effect = killing(listen, ("r2", "r1"))

    run(tmp_path, report, concurrency=2, listen=listen)

    collaborators["killpg"].assert_called_once_with(1, SIGTERM)
    assert {"event": "stopping run", "run": "r1"} in reported(report)
    assert started_runs(report) == ["r1", "r2", "r3"]


def test_a_second_kill_sends_sigkill(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()
    planning(collaborators, 1)
    collaborators["execute_run"].side_effect = killing(
        listen, ("r1", "r1"), ("r1", "r1")
    )

    run(tmp_path, report, listen=listen)

    assert collaborators["killpg"].call_args_list == [
        mock.call(1, SIGTERM),
        mock.call(1, SIGKILL),
    ]
    assert events(report) == [
        "planned",
        "started",
        "stopping run",
        "killing run",
        "ended",
        "idle",
    ]


def test_killing_a_run_that_is_not_running_does_nothing(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()
    planning(collaborators, 2)
    collaborators["execute_run"].side_effect = killing(listen, ("r1", "r2"))

    run(tmp_path, report, listen=listen)
    listen.call_args.args[0].kill("r1")

    collaborators["killpg"].assert_not_called()
    assert events(report) == ["planned", "started", "ended", "started", "ended", "idle"]


def test_a_second_interrupt_after_the_processes_exit_kills_nothing(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()

    async def execute(
        root: Path,
        folder: Path,
        command: str,
        params: object,
        running: set[object],
        stopping: asyncio.Event,
        invocation: str,
    ) -> dict[str, object]:
        running.add(mock.Mock(pid=42))
        listen.call_args.args[0].interrupt()
        running.clear()
        listen.call_args.args[0].interrupt()
        return {"exit_code": -15, "error": None}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, listen=listen)

    collaborators["killpg"].assert_called_once_with(42, SIGTERM)
    assert events(report) == ["planned", "started", "stopping", "ended", "idle"]


def test_waits_for_finish_once_idle(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    heard: list[Any] = []

    async def go() -> None:
        config = mock.Mock(root=tmp_path, runs="{experiment}/{run}")
        report = mock.Mock()
        task = asyncio.create_task(
            run_experiment(config, "exp", experiment(), 1, report, heard.append)
        )
        while {"event": "idle"} not in reported(report):
            await asyncio.sleep(0.001)
        await asyncio.sleep(0.01)
        assert not task.done()
        heard[0].finish()
        assert len(await task) == 2

    asyncio.run(go())


def test_retry_runs_an_ended_run_again_under_a_new_id(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()

    async def execute(root: Path, folder: Path, *args: object) -> dict[str, object]:
        if folder.name == "r2":
            listen.call_args.args[0].retry("r1")
        return {"exit_code": 0, "error": None}

    collaborators["execute_run"].side_effect = execute

    results = run(tmp_path, report, listen=listen)

    assert len(results) == 3
    assert started_runs(report) == ["r1", "r2", "r3"]
    retried = {"event": "retried", "run": "r1", "retry": "r3", "params": A}
    assert retried in reported(report)
    assert collaborators["execute_run"].await_args_list[2].args[3] == A
    assert collaborators["new_run_id"].call_args_list[2].args[0]("r3")


def test_retry_ignores_runs_that_have_not_ended(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()

    async def execute(root: Path, folder: Path, *args: object) -> dict[str, object]:
        listen.call_args.args[0].retry(folder.name)
        return {"exit_code": 0, "error": None}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, listen=listen)

    assert started_runs(report) == ["r1", "r2"]


def test_retry_does_nothing_after_stopping(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()

    async def execute(root: Path, folder: Path, *args: object) -> dict[str, object]:
        if folder.name == "r2":
            controls = listen.call_args.args[0]
            controls.interrupt()
            controls.retry("r1")
        return {"exit_code": 0, "error": None}

    collaborators["execute_run"].side_effect = execute
    collaborators["plan_runs"].return_value = [A, B, A]

    run(tmp_path, report, listen=listen)

    assert started_runs(report) == ["r1", "r2"]
    assert "retried" not in events(report)
