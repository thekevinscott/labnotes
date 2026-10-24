import asyncio
import inspect
from collections.abc import Callable, Coroutine, Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.runner.run_experiment import run_experiment

A: dict[str, object] = {"m": "a"}
B: dict[str, object] = {"m": "b"}
SIGKILL, SIGTERM = 9, 15


def settle[T](work: Coroutine[Any, Any, T]) -> T:
    # A broken retry budget or cancel waits on a timer or never ends; fail fast.
    return asyncio.run(asyncio.wait_for(work, 5))


def experiment(mode: str = "matrix", retries: int = 2) -> mock.Mock:
    config = mock.Mock(
        command="run",
        params={"m": ["a", "b"]},
        repeats=2,
        counts="c",
        mode=mode,
        retries=retries,
        meta=None,
    )
    config.name = None
    return config


@pytest.fixture
def collaborators(tmp_path: Path) -> Iterator[dict[str, mock.MagicMock]]:
    names = iter(["n1", "n2", "n3"])
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
            "labnotes.runner.run_experiment.experiment_run_ids",
            new=mock.AsyncMock(return_value=set()),
        ) as run_ids,
        mock.patch(
            "labnotes.runner.run_experiment.param_grid", return_value=[A, B]
        ) as param_grid,
        mock.patch(
            "labnotes.runner.run_experiment.plan_runs", return_value=[A, B]
        ) as plan_runs,
        mock.patch(
            "labnotes.runner.run_experiment.new_stamped_run_id",
            side_effect=lambda taken: next(ids),
        ) as new_stamped_run_id,
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
        mock.patch("labnotes.runner.run_experiment.signal_tree") as signal_tree,
        mock.patch(
            "labnotes.runner.run_experiment.new_param_run_id",
            side_effect=lambda params, choices, taken: next(names),
        ) as new_param_run_id,
        mock.patch(
            "labnotes.runner.run_experiment.invocation_meta",
            new=mock.AsyncMock(return_value={"commit": "abc"}),
        ) as invocation_meta,
    ):
        yield {
            "open_tables": open_tables,
            "list_runs": list_runs,
            "run_ids": run_ids,
            "param_grid": param_grid,
            "plan_runs": plan_runs,
            "new_stamped_run_id": new_stamped_run_id,
            "new_param_run_id": new_param_run_id,
            "execute_run": execute_run,
            "signal_tree": signal_tree,
            "invocation_meta": invocation_meta,
        }


def run(
    tmp_path: Path,
    report: mock.Mock,
    concurrency: int = 1,
    listen: mock.Mock | None = None,
    mode: str = "matrix",
    retries: int = 2,
    retry_seconds: float = 0.0,
) -> list[dict[str, object]]:
    config = mock.Mock(root=tmp_path, runs="{experiment}/{run}")
    hear = mock.Mock() if listen is None else listen

    def listening(controls: object) -> None:
        hear(controls)
        controls.finish()  # type: ignore[attr-defined]

    return settle(
        run_experiment(
            config,
            "exp",
            experiment(mode, retries),
            concurrency,
            report,
            listening,
            retry_seconds=retry_seconds,
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


def test_adhoc_plans_every_run_again(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    run(tmp_path, mock.Mock(), mode="adhoc")

    collaborators["run_ids"].assert_awaited_once_with(
        collaborators["open_tables"].return_value, "exp"
    )
    collaborators["list_runs"].assert_not_awaited()
    collaborators["plan_runs"].assert_called_once_with([A, B], 2, [])


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
    ended = {"exit_code": 0, "error": None}
    assert [c.args[0] for c in report.call_args_list] == [
        {
            "event": "planned",
            "title": "exp",
            "runs": [{"run": "r1", "params": A}, {"run": "r2", "params": B}],
            "concurrency": 1,
            "mode": "matrix",
        },
        {
            "event": "started",
            "run": "r1",
            "params": A,
            "folder": tmp_path / "exp" / "r1",
        },
        {"event": "ended", "run": "r1", **ended},
        {
            "event": "started",
            "run": "r2",
            "params": B,
            "folder": tmp_path / "exp" / "r2",
        },
        {"event": "ended", "run": "r2", **ended},
        {"event": "idle"},
    ]


def start_with_meta(tmp_path: Path, report: mock.Mock) -> list[dict[str, object]]:
    configured = experiment()
    configured.meta = "git log -1"
    return settle(
        run_experiment(
            mock.Mock(root=tmp_path, runs="{experiment}/{run}"),
            "exp",
            configured,
            1,
            report,
            lambda controls: controls.finish(),  # type: ignore[attr-defined]
        )
    )


def test_runs_without_meta_when_none_is_configured(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    run(tmp_path, mock.Mock())

    collaborators["invocation_meta"].assert_not_awaited()
    calls = collaborators["execute_run"].await_args_list
    assert [c.kwargs["meta"] for c in calls] == [None, None]


def test_gives_every_run_the_meta_read_once_at_the_start(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    start_with_meta(tmp_path, mock.Mock())

    collaborators["invocation_meta"].assert_awaited_once_with(tmp_path, "git log -1")
    calls = collaborators["execute_run"].await_args_list
    assert [c.kwargs["meta"] for c in calls] == [{"commit": "abc"}] * 2


def test_fails_before_planning_when_the_meta_command_fails(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["invocation_meta"].side_effect = ValueError("meta failed")
    report = mock.Mock()

    with pytest.raises(ValueError, match="meta failed"):
        start_with_meta(tmp_path, report)

    report.assert_not_called()
    collaborators["open_tables"].assert_not_called()
    collaborators["execute_run"].assert_not_awaited()


def test_titles_the_plan_with_the_experiments_name(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    report = mock.Mock()
    named = experiment()
    named.name = "Model effort"

    settle(
        run_experiment(
            mock.Mock(root=tmp_path, runs="{experiment}/{run}"),
            "exp",
            named,
            1,
            report,
            lambda controls: controls.finish(),  # type: ignore[attr-defined]
        )
    )

    assert report.call_args_list[0].args[0]["title"] == "Model effort"


def test_checks_new_stamped_run_ids_against_existing_runs(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["run_ids"].return_value = {"taken"}

    run(tmp_path, mock.Mock())

    taken = collaborators["new_stamped_run_id"].call_args.args[0]
    assert (taken("taken"), taken("free")) == (True, False)


def test_nests_adhoc_runs_in_one_folder_per_command(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["run_ids"].return_value = {"r1", "r1/taken"}
    listen, report = mock.Mock(), mock.Mock()

    async def execute(
        root: Path, folder: Path, *args: object, **_: object
    ) -> dict[str, object]:
        if folder.name == "n2":
            listen.call_args.args[0].retry("r1/n1")
        return {"exit_code": 0, "error": None}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, listen=listen, mode="adhoc")

    assert started_runs(report) == ["r1/n1", "r1/n2", "r1/n3"]
    assert (tmp_path / "exp" / "r1" / "n1").is_dir()
    assert collaborators["new_stamped_run_id"].call_count == 1
    group_taken = collaborators["new_stamped_run_id"].call_args.args[0]
    assert (group_taken("r1"), group_taken("free")) == (True, False)
    taken = collaborators["new_param_run_id"].call_args.args[2]
    assert (taken("taken"), taken("n1"), taken("free")) == (True, True, False)
    named = [c.args[:2] for c in collaborators["new_param_run_id"].call_args_list]
    choices = {"m": ["a", "b"]}
    assert named == [(A, choices), (B, choices), (A, choices)]


def test_gives_a_lone_adhoc_run_its_own_stamped_folder(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["plan_runs"].return_value = [A]
    listen = mock.Mock()

    def retry_first(event: dict[str, object]) -> None:
        if event == {"event": "ended", "run": "r1", "exit_code": 0, "error": None}:
            retry = listen.call_args.args[0].retry
            asyncio.get_running_loop().call_soon(retry, "r1")

    report = mock.Mock(side_effect=retry_first)

    run(tmp_path, report, listen=listen, mode="adhoc")

    assert started_runs(report) == ["r1", "r2"]
    assert (tmp_path / "exp" / "r1").is_dir()
    collaborators["new_param_run_id"].assert_not_called()


def test_stamps_no_folder_when_an_adhoc_command_plans_nothing(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["plan_runs"].return_value = []

    run(tmp_path, mock.Mock(), mode="adhoc")

    collaborators["new_stamped_run_id"].assert_not_called()


def test_names_every_run_before_the_first_starts(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    def started(taken: object) -> str:
        assert not collaborators["execute_run"].await_count
        return next(ids)

    ids = iter(["r1", "r2"])
    collaborators["new_stamped_run_id"].side_effect = started

    run(tmp_path, mock.Mock())

    taken = collaborators["new_stamped_run_id"].call_args.args[0]
    assert (taken("r1"), taken("r2")) == (True, True)


def test_runs_up_to_the_concurrency_at_once(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    live: list[int] = []
    peak = 0

    async def execute(*args: object, **_: object) -> dict[str, object]:
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
        tree: set[object],
        retry_of: str | None,
        **__: object,
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
    collaborators["signal_tree"].assert_called_once_with(42, SIGTERM, set())
    assert events(report) == ["planned", "started", "stopping", "ended", "idle"]


def test_second_interrupt_kills_runs(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen = mock.Mock()
    collaborators["execute_run"].side_effect = interrupting(2, listen)
    report = mock.Mock()

    run(tmp_path, report, listen=listen)

    assert collaborators["signal_tree"].call_args_list == [
        mock.call(42, SIGTERM, set()),
        mock.call(42, SIGKILL, set()),
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

    collaborators["signal_tree"].assert_called_once_with(42, SIGTERM, set())
    assert events(report) == ["planned", "started", "stopping", "ended", "idle"]


def test_signals_the_tree_the_run_waits_on(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen = mock.Mock()
    collaborators["execute_run"].side_effect = interrupting(1, listen)

    run(tmp_path, mock.Mock(), listen=listen)

    tree = collaborators["execute_run"].await_args.args[6]
    assert collaborators["signal_tree"].call_args.args[2] is tree


def test_moves_a_pending_run_to_the_front(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen = mock.Mock()
    report = mock.Mock()

    async def execute(*args: object, **_: object) -> dict[str, object]:
        controls = listen.call_args.args[0]
        controls.run_next("r1")
        # Built at runtime, so an `is` comparison would miss it.
        controls.run_next("".join(["r", "4"]))
        return {"exit_code": 0, "error": None}

    ids = iter(["r1", "r2", "r3", "r4"])
    collaborators["new_stamped_run_id"].side_effect = lambda taken: next(ids)
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


@pytest.mark.parametrize(
    ("place", "started", "pending"),
    [
        (1, ["r1", "r3", "r2", "r4"], ["r3", "r2", "r4"]),
        (-1, ["r1", "r2", "r3", "r4"], ["r2", "r3", "r4"]),
        (0, ["r1", "r2", "r3", "r4"], ["r2", "r3", "r4"]),
        (9, ["r1", "r3", "r4", "r2"], ["r3", "r4", "r2"]),
    ],
)
def test_moves_a_pending_run_to_a_place_in_the_queue(
    tmp_path: Path,
    collaborators: dict[str, mock.MagicMock],
    place: int,
    started: list[str],
    pending: list[str],
) -> None:
    listen, report = mock.Mock(), mock.Mock()
    planning(collaborators, 4)

    async def execute(
        root: Path, folder: Path, *args: object, **_: object
    ) -> dict[str, object]:
        if folder.name == "r1":
            controls = listen.call_args.args[0]
            controls.move("r1", 0)
            controls.move("".join(["r", "2"]), place)
        return {"exit_code": 0, "error": None}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, listen=listen)

    assert started_runs(report) == started
    moved = {"event": "moved", "run": "r2", "pending": pending, "held": []}
    assert moved in reported(report)
    assert events(report).count("moved") == 1


def changing_concurrency(listen: mock.Mock, to: int, widths: list[int]) -> object:
    live = 0

    async def execute(*args: object, **_: object) -> dict[str, object]:
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
    collaborators["new_stamped_run_id"].side_effect = lambda taken: next(ids)
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
    collaborators["new_stamped_run_id"].side_effect = lambda taken: next(ids)
    collaborators["plan_runs"].return_value = [A, B] * (count // 2) + [A] * (count % 2)


def started_runs(report: mock.Mock) -> list[object]:
    return [e["run"] for e in reported(report) if e["event"] == "started"]


def test_a_deselected_run_does_not_run(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()
    planning(collaborators, 3)

    async def execute(
        root: Path, folder: Path, *args: object, **_: object
    ) -> dict[str, object]:
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

    async def execute(*args: object, **_: object) -> dict[str, object]:
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

    async def execute(
        root: Path, folder: Path, *args: object, **_: object
    ) -> dict[str, object]:
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

    async def execute(*args: object, **_: object) -> dict[str, object]:
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

    async def execute(*args: object, **_: object) -> dict[str, object]:
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
        tree: set[object],
        retry_of: str | None,
        **__: object,
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

    collaborators["signal_tree"].assert_called_once_with(1, SIGTERM, set())
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

    assert collaborators["signal_tree"].call_args_list == [
        mock.call(1, SIGTERM, set()),
        mock.call(1, SIGKILL, set()),
    ]
    assert events(report) == [
        "planned",
        "started",
        "stopping run",
        "killing run",
        "ended",
        "idle",
    ]


def test_tells_each_run_whether_it_was_stopped(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()
    planning(collaborators, 2)
    seen: list[tuple[str, bool, bool]] = []

    async def execute(
        root: Path,
        folder: Path,
        command: str,
        params: object,
        running: set[object],
        stopping: asyncio.Event,
        tree: set[object],
        retry_of: str | None,
        *,
        stopped: Callable[[], bool],
        **__: object,
    ) -> dict[str, object]:
        running.add(mock.Mock(pid=1))
        before = stopped()
        if folder.name == "r1":
            listen.call_args.args[0].kill("r1")
        seen.append((folder.name, before, stopped()))
        running.clear()
        return {"exit_code": 0, "error": None}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, listen=listen)

    assert seen == [("r1", False, True), ("r2", False, False)]


def test_killing_a_run_that_is_not_running_does_nothing(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()
    planning(collaborators, 2)
    collaborators["execute_run"].side_effect = killing(listen, ("r1", "r2"))

    run(tmp_path, report, listen=listen)
    listen.call_args.args[0].kill("r1")

    collaborators["signal_tree"].assert_not_called()
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
        tree: set[object],
        retry_of: str | None,
        **__: object,
    ) -> dict[str, object]:
        running.add(mock.Mock(pid=42))
        listen.call_args.args[0].interrupt()
        running.clear()
        listen.call_args.args[0].interrupt()
        return {"exit_code": -15, "error": None}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, listen=listen)

    collaborators["signal_tree"].assert_called_once_with(42, SIGTERM, set())
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

    settle(go())


def test_retry_runs_an_ended_run_again_under_a_new_id(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()

    async def execute(
        root: Path, folder: Path, *args: object, **_: object
    ) -> dict[str, object]:
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
    assert collaborators["new_stamped_run_id"].call_args_list[2].args[0]("r3")


def test_retry_ignores_runs_that_have_not_ended(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()

    async def execute(
        root: Path, folder: Path, *args: object, **_: object
    ) -> dict[str, object]:
        listen.call_args.args[0].retry(folder.name)
        return {"exit_code": 0, "error": None}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, listen=listen)

    assert started_runs(report) == ["r1", "r2"]


def test_retry_does_nothing_after_stopping(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen, report = mock.Mock(), mock.Mock()

    async def execute(
        root: Path, folder: Path, *args: object, **_: object
    ) -> dict[str, object]:
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


def test_passes_the_timeout_to_each_run(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    asyncio.run(
        run_experiment(
            mock.Mock(root=tmp_path, runs="{experiment}/{run}"),
            "exp",
            experiment(),
            1,
            mock.Mock(),
            lambda controls: controls.finish(),
            90,
        )
    )

    calls = collaborators["execute_run"].await_args_list
    assert [c.kwargs["timeout"] for c in calls] == [90, 90]


def test_a_timed_out_run_stops_like_a_kill(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    report = mock.Mock()
    planning(collaborators, 1)

    async def execute(
        root: Path,
        folder: Path,
        command: str,
        params: object,
        running: set[object],
        stopping: asyncio.Event,
        tree: set[object],
        retry_of: str | None,
        *,
        stop: Callable[[], None],
        **__: object,
    ) -> dict[str, object]:
        running.add(mock.Mock(pid=1))
        stop()
        stop()
        running.clear()
        stop()
        return {"exit_code": -9, "error": "timed out after 1s"}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report)

    assert collaborators["signal_tree"].call_args_list == [
        mock.call(1, SIGTERM, set()),
        mock.call(1, SIGKILL, set()),
    ]
    assert events(report) == [
        "planned",
        "started",
        "stopping run",
        "killing run",
        "ended",
        "idle",
    ]


def test_never_retries_a_run_that_timed_out(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["plan_runs"].return_value = [A]
    report = mock.Mock()

    async def execute(
        root: Path,
        folder: Path,
        command: str,
        params: object,
        running: set[object],
        *args: object,
        stop: Callable[[], None],
        **_: object,
    ) -> dict[str, object]:
        running.add(mock.Mock(pid=1))
        stop()
        return {"exit_code": 75, "error": "timed out after 1s"}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, retry_seconds=0.01)

    assert events(report) == ["planned", "started", "stopping run", "ended", "idle"]


def exiting(*codes: int) -> object:
    exits = iter(codes)

    async def execute(*args: object, **_: object) -> dict[str, object]:
        return {"exit_code": next(exits), "error": None}

    return execute


def retry_parents(collaborators: dict[str, mock.MagicMock]) -> list[object]:
    return [c.args[7] for c in collaborators["execute_run"].await_args_list]


def test_waits_thirty_seconds_before_a_retry_by_default() -> None:
    default = inspect.signature(run_experiment).parameters["retry_seconds"].default

    assert default == 30.0


def test_retries_a_tempfail_with_the_same_params(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["plan_runs"].return_value = [A]
    collaborators["execute_run"].side_effect = exiting(75, 0)
    report = mock.Mock()

    results = run(tmp_path, report, retry_seconds=0.01)

    assert [r["exit_code"] for r in results] == [75, 0]
    assert started_runs(report) == ["r1", "r2"]
    assert [c.args[3] for c in collaborators["execute_run"].await_args_list] == [A, A]
    assert retry_parents(collaborators) == [None, "r1"]
    assert events(report) == [
        "planned",
        "started",
        "ended",
        "retrying",
        "retried",
        "started",
        "ended",
        "idle",
    ]
    retrying = {
        "event": "retrying",
        "run": "r1",
        "attempt": 1,
        "retries": 2,
        "seconds": 0.01,
    }
    assert retrying in reported(report)
    assert {"event": "retried", "run": "r1", "retry": "r2", "params": A} in reported(
        report
    )


def test_doubles_the_wait_then_gives_up(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    planning(collaborators, 1)
    collaborators["new_stamped_run_id"].side_effect = iter(["r1", "r2", "r3"])
    collaborators["execute_run"].side_effect = exiting(75, 75, 75)
    report = mock.Mock()

    run(tmp_path, report, retry_seconds=0.01)

    assert started_runs(report) == ["r1", "r2", "r3"]
    assert retry_parents(collaborators) == [None, "r1", "r2"]
    waits = [e for e in reported(report) if e["event"] == "retrying"]
    assert [(e["run"], e["attempt"], e["seconds"]) for e in waits] == [
        ("r1", 1, 0.01),
        ("r2", 2, 0.02),
    ]
    assert reported(report)[-2:] == [
        {"event": "gave up", "run": "r3", "retries": 2},
        {"event": "idle"},
    ]


def test_gives_up_at_once_with_no_retries(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["plan_runs"].return_value = [A]
    collaborators["execute_run"].side_effect = exiting(75)
    report = mock.Mock()

    run(tmp_path, report, retries=0)

    assert started_runs(report) == ["r1"]
    assert {"event": "gave up", "run": "r1", "retries": 0} in reported(report)


@pytest.mark.parametrize("code", [1, 74, 76, -15, 0])
def test_never_retries_other_exits(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock], code: int
) -> None:
    collaborators["plan_runs"].return_value = [A]
    collaborators["execute_run"].side_effect = exiting(code)
    report = mock.Mock()

    run(tmp_path, report)

    assert events(report) == ["planned", "started", "ended", "idle"]


def test_never_retries_a_run_that_failed_to_start(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["plan_runs"].return_value = [A]
    collaborators["execute_run"].return_value = {"exit_code": None, "error": "boom"}
    report = mock.Mock()

    run(tmp_path, report)

    assert events(report) == ["planned", "started", "ended", "idle"]


def test_never_retries_a_stopped_run(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["plan_runs"].return_value = [A]
    listen, report = mock.Mock(), mock.Mock()

    async def execute(
        root: Path,
        folder: Path,
        command: str,
        params: object,
        running: set[object],
        *args: object,
        **_: object,
    ) -> dict[str, object]:
        running.add(mock.Mock(pid=42))
        listen.call_args.args[0].kill("r1")
        return {"exit_code": 75, "error": None}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, listen=listen)

    assert events(report) == ["planned", "started", "stopping run", "ended", "idle"]


def test_never_retries_once_stopping(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["plan_runs"].return_value = [A]
    listen, report = mock.Mock(), mock.Mock()

    async def execute(*args: object, **_: object) -> dict[str, object]:
        listen.call_args.args[0].interrupt()
        return {"exit_code": 75, "error": None}

    collaborators["execute_run"].side_effect = execute

    run(tmp_path, report, listen=listen)

    assert events(report) == ["planned", "started", "stopping", "ended", "idle"]


def calling(action: str, *args: object) -> tuple[mock.Mock, mock.Mock]:
    listen = mock.Mock()

    def on_retrying(event: dict[str, object]) -> None:
        if event["event"] == "retrying":
            control = getattr(listen.call_args.args[0], action)
            asyncio.get_running_loop().call_soon(control, *args)

    return listen, mock.Mock(side_effect=on_retrying)


def test_stopping_cancels_a_waiting_retry(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["plan_runs"].return_value = [A]
    collaborators["execute_run"].side_effect = exiting(75)
    listen, report = calling("interrupt")

    run(tmp_path, report, listen=listen, retry_seconds=60)

    assert started_runs(report) == ["r1"]
    assert reported(report)[-3:] == [
        {"event": "stopping"},
        {"event": "retry cancelled", "run": "r1"},
        {"event": "idle"},
    ]


def test_stopping_with_runs_going_cancels_waiting_retries_too(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen = mock.Mock()
    release = asyncio.Event()

    async def execute(
        root: Path, folder: Path, *args: object, **_: object
    ) -> dict[str, object]:
        if folder.name == "r1":
            return {"exit_code": 75, "error": None}
        await release.wait()
        return {"exit_code": -15, "error": None}

    def on_event(event: dict[str, object]) -> None:
        match event["event"]:
            case "retrying":
                interrupt = listen.call_args.args[0].interrupt
                asyncio.get_running_loop().call_soon(interrupt)
            case "retry cancelled":
                release.set()

    collaborators["execute_run"].side_effect = execute
    report = mock.Mock(side_effect=on_event)

    run(tmp_path, report, listen=listen, concurrency=2, retry_seconds=60)

    assert started_runs(report) == ["r1", "r2"]
    assert events(report)[-4:] == ["stopping", "retry cancelled", "ended", "idle"]


def test_killing_a_waiting_retry_cancels_it(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["plan_runs"].return_value = [A]
    collaborators["execute_run"].side_effect = exiting(75)
    listen, report = calling("kill", "r1")

    run(tmp_path, report, listen=listen, retry_seconds=60)

    assert started_runs(report) == ["r1"]
    assert reported(report)[-2:] == [
        {"event": "retry cancelled", "run": "r1"},
        {"event": "idle"},
    ]


def test_retrying_a_waiting_run_starts_it_now_and_spends_the_budget(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["plan_runs"].return_value = [A]
    collaborators["execute_run"].side_effect = exiting(75, 75)
    listen, report = calling("retry", "r1")

    run(tmp_path, report, listen=listen, retries=1, retry_seconds=60)

    assert started_runs(report) == ["r1", "r2"]
    assert retry_parents(collaborators) == [None, "r1"]
    assert "retry cancelled" not in events(report)
    assert {"event": "gave up", "run": "r2", "retries": 1} in reported(report)


def test_each_retry_of_a_waiting_run_spends_one_more_of_the_budget(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["plan_runs"].return_value = [A]
    collaborators["execute_run"].side_effect = exiting(75, 75, 75, 75)
    collaborators["new_stamped_run_id"].side_effect = iter(["r1", "r2", "r3", "r4"])
    listen = mock.Mock()

    def retry_at_once(event: dict[str, object]) -> None:
        if event["event"] == "retrying":
            retry = listen.call_args.args[0].retry
            asyncio.get_running_loop().call_soon(retry, event["run"])

    report = mock.Mock(side_effect=retry_at_once)

    run(tmp_path, report, listen=listen, retries=2, retry_seconds=60)

    assert started_runs(report) == ["r1", "r2", "r3"]
    assert {"event": "gave up", "run": "r3", "retries": 2} in reported(report)


def test_a_manual_retry_links_to_its_run_with_a_fresh_budget(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["plan_runs"].return_value = [A]
    collaborators["execute_run"].side_effect = exiting(75, 75, 75)
    collaborators["new_stamped_run_id"].side_effect = iter(["r1", "r2", "r3"])
    listen = mock.Mock()

    def retry_after_giving_up(event: dict[str, object]) -> None:
        if event == {"event": "gave up", "run": "r1", "retries": 0}:
            retry = listen.call_args.args[0].retry
            asyncio.get_running_loop().call_soon(retry, "r1")

    report = mock.Mock(side_effect=retry_after_giving_up)

    async def go() -> None:
        config = mock.Mock(root=tmp_path, runs="{experiment}/{run}")
        controls: list[Any] = []

        def hear(heard: Any) -> None:
            listen(heard)
            controls.append(heard)

        task = asyncio.create_task(
            run_experiment(
                config, "exp", experiment(retries=0), 1, report, hear, retry_seconds=0
            )
        )
        while len(started_runs(report)) < 2 or "idle" not in events(report)[-1:]:
            await asyncio.sleep(0.001)
        controls[0].finish()
        await task

    settle(go())

    assert retry_parents(collaborators) == [None, "r1"]
    assert {"event": "gave up", "run": "r2", "retries": 0} in reported(report)
