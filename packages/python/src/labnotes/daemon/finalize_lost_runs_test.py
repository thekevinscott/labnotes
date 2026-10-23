import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.daemon.finalize_lost_runs import finalize_lost_runs

CONFIG = mock.Mock(root=Path("/lab"))
GOING = {"params": {"n": 1}, "ended": None, "exit_code": None, "error": None}
LOST = {"ended": "1970-01-01T00:01:40Z", "ended_by": "lost"}


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.daemon.finalize_lost_runs.open_tables") as open_tables,
        mock.patch("labnotes.daemon.finalize_lost_runs.process_alive") as alive,
        mock.patch("labnotes.daemon.finalize_lost_runs.write_run_json") as write,
        mock.patch("labnotes.daemon.finalize_lost_runs.time") as time,
        mock.patch("labnotes.daemon.finalize_lost_runs.UNFINISHED", "unfinished"),
    ):
        time.time.return_value = 100
        open_tables.return_value.query = mock.AsyncMock(return_value=[])
        yield {"open_tables": open_tables, "alive": alive, "write": write}


def finalize(
    collaborators: dict[str, mock.MagicMock], *runs: dict[str, object]
) -> None:
    collaborators["open_tables"].return_value.query.return_value = [
        {"folder": f"a/runs/r{n}", "run": json.dumps(run)} for n, run in enumerate(runs)
    ]
    asyncio.run(finalize_lost_runs(CONFIG))


def test_reads_only_unfinished_runs(collaborators: dict[str, mock.MagicMock]) -> None:
    finalize(collaborators)

    collaborators["open_tables"].assert_called_once_with(CONFIG)
    collaborators["open_tables"].return_value.query.assert_awaited_once_with(
        "SELECT folder, run FROM runs WHERE unfinished"
    )
    collaborators["write"].assert_not_called()


def test_ends_a_run_whose_process_is_gone(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["alive"].return_value = False
    run: dict[str, object] = {**GOING, "pid": 7, "pid_created": 12.5, "note": "kept"}

    finalize(collaborators, run)

    collaborators["alive"].assert_called_once_with(7, 12.5)
    collaborators["write"].assert_called_once_with(
        Path("/lab/a/runs/r0"), {**run, **LOST}
    )


def test_leaves_a_run_whose_process_still_runs(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["alive"].return_value = True

    finalize(collaborators, {**GOING, "pid": 7, "pid_created": 12})

    collaborators["alive"].assert_called_once_with(7, 12)
    collaborators["write"].assert_not_called()


@pytest.mark.parametrize("created", [{}, {"pid_created": None}, {"pid_created": "x"}])
def test_checks_a_pid_without_a_usable_start_time(
    collaborators: dict[str, mock.MagicMock], created: dict[str, object]
) -> None:
    collaborators["alive"].return_value = True

    finalize(collaborators, {**GOING, "pid": 7, **created})

    collaborators["alive"].assert_called_once_with(7, None)


@pytest.mark.parametrize("pid", [{}, {"pid": None}, {"pid": "7"}])
def test_ends_a_run_that_never_launched(
    collaborators: dict[str, mock.MagicMock], pid: dict[str, object]
) -> None:
    run = {**GOING, **pid}

    finalize(collaborators, run)

    collaborators["alive"].assert_not_called()
    collaborators["write"].assert_called_once_with(
        Path("/lab/a/runs/r0"), {**run, **LOST}
    )


def test_checks_every_unfinished_run(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["alive"].side_effect = [True, False]

    finalize(collaborators, {**GOING, "pid": 1}, {**GOING, "pid": 2})

    [(folder, _)] = [c.args for c in collaborators["write"].call_args_list]
    assert folder == Path("/lab/a/runs/r1")
