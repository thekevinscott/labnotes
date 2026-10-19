import asyncio
from collections.abc import Iterator
from pathlib import Path
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
    return asyncio.run(
        run_experiment(
            config,
            "exp",
            experiment(),
            concurrency,
            report,
            mock.Mock() if listen is None else listen,
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
    assert events(report) == ["planned", "started", "stopping", "ended"]


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
    assert events(report) == ["planned", "started", "stopping", "killing", "ended"]


def test_a_late_interrupt_after_the_runs_end_does_nothing(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    listen = mock.Mock()
    collaborators["execute_run"].side_effect = interrupting(1, listen)
    report = mock.Mock()

    run(tmp_path, report, listen=listen)
    listen.call_args.args[0].interrupt()

    collaborators["killpg"].assert_called_once_with(42, SIGTERM)
    assert events(report) == ["planned", "started", "stopping", "ended"]


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
    queued = {"event": "queued", "run": "r4", "pending": ["r4", "r2", "r3"]}
    assert reported[2] == queued
    assert events(report).count("queued") == 1
