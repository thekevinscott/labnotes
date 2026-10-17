import asyncio
import os
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.run_experiment import run_experiment

A: dict[str, object] = {"m": "a"}
B: dict[str, object] = {"m": "b"}
SIGINT, SIGKILL, SIGTERM = 2, 9, 15


def experiment() -> mock.Mock:
    return mock.Mock(command="run", params={"m": ["a", "b"]}, repeats=2)


@pytest.fixture
def collaborators(tmp_path: Path) -> Iterator[dict[str, mock.MagicMock]]:
    ids = iter(["r1", "r2", "r3"])
    with (
        mock.patch("labnotes.runner.run_experiment.open_tables") as open_tables,
        mock.patch(
            "labnotes.runner.run_experiment.list_experiment_runs",
            new=mock.AsyncMock(
                return_value=[
                    {"params": '{"m": "a"}', "exit_code": 0},
                    {"params": '{"m": "b"}', "exit_code": 1},
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
            "labnotes.runner.run_experiment.param_args",
            side_effect=lambda params: ["--m", params["m"]],
        ),
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
            mock.Mock(SIGINT=SIGINT, SIGTERM=SIGTERM, SIGKILL=SIGKILL),
        ),
        mock.patch("labnotes.runner.run_experiment.os.killpg") as killpg,
        mock.patch("labnotes.runner.run_experiment.os._exit") as exit_,
    ):
        yield {
            "open_tables": open_tables,
            "list_runs": list_runs,
            "param_grid": param_grid,
            "plan_runs": plan_runs,
            "new_run_id": new_run_id,
            "execute_run": execute_run,
            "killpg": killpg,
            "exit": exit_,
        }


def run(
    tmp_path: Path, report: mock.Mock, concurrency: int = 1
) -> list[dict[str, object]]:
    config = mock.Mock(root=tmp_path, runs="{experiment}/{run}")
    return asyncio.run(run_experiment(config, "exp", experiment(), concurrency, report))


def test_plans_the_runs_still_needed(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    run(tmp_path, mock.Mock())

    collaborators["list_runs"].assert_awaited_once_with(
        collaborators["open_tables"].return_value, "exp"
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
    assert [c.args[:3] for c in calls] == [
        (tmp_path / "exp" / "r1", "run", A),
        (tmp_path / "exp" / "r2", "run", B),
    ]
    assert (tmp_path / "exp" / "r1").is_dir()
    assert [c.args[0] for c in report.call_args_list] == [
        "2 runs to go, 1 at a time.",
        "r1 started --m a",
        "r1 exited 0",
        "r2 started --m b",
        "r2 exited 0",
    ]


def test_checks_new_run_ids_against_existing_folders(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    (tmp_path / "exp" / "taken").mkdir(parents=True)

    run(tmp_path, mock.Mock())

    taken = collaborators["new_run_id"].call_args.args[0]
    assert (taken("taken"), taken("free")) == (True, False)


def test_reports_a_run_that_could_not_start(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["execute_run"].return_value = {"exit_code": None, "error": "boom"}
    report = mock.Mock()

    run(tmp_path, report)

    assert report.call_args_list[2].args[0] == "r1 boom"


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


def interrupting(times: int) -> object:
    async def execute(
        folder: Path, command: str, params: object, running: set[object]
    ) -> dict[str, object]:
        running.add(mock.Mock(pid=42))
        for _ in range(times):
            os.kill(os.getpid(), SIGINT)
            for _ in range(20):
                await asyncio.sleep(0)
        running.clear()
        return {"exit_code": -15, "error": None}

    return execute


def test_first_ctrl_c_stops_runs_and_starts_no_more(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["execute_run"].side_effect = interrupting(1)
    report = mock.Mock()

    assert run(tmp_path, report) == [{"exit_code": -15, "error": None}]

    collaborators["killpg"].assert_called_once_with(42, SIGTERM)
    collaborators["exit"].assert_not_called()
    assert "Stopping runs. Ctrl-C again to kill them." in [
        c.args[0] for c in report.call_args_list
    ]


def test_second_ctrl_c_kills_runs_and_exits(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["execute_run"].side_effect = interrupting(2)

    run(tmp_path, mock.Mock())

    assert collaborators["killpg"].call_args_list == [
        mock.call(42, SIGTERM),
        mock.call(42, SIGKILL),
    ]
    collaborators["exit"].assert_called_once_with(130)


def test_ignores_a_run_that_already_exited(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["execute_run"].side_effect = interrupting(1)
    collaborators["killpg"].side_effect = ProcessLookupError

    run(tmp_path, mock.Mock())
