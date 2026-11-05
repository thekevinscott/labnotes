import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.finalize_lost_runs import finalize_lost_runs

GOING: dict[str, object] = {"params": {"n": 1}, "ended": None, "exit_code": None}


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.runner.finalize_lost_runs.open_tables") as open_tables,
        mock.patch("labnotes.runner.finalize_lost_runs.process_alive") as alive,
        mock.patch("labnotes.runner.finalize_lost_runs.mark_lost") as mark,
        mock.patch("labnotes.runner.finalize_lost_runs.claim_run") as claim,
        mock.patch("labnotes.runner.finalize_lost_runs.os") as os_mod,
        mock.patch("labnotes.runner.finalize_lost_runs.UNFINISHED", "unfinished"),
    ):
        open_tables.return_value.query = mock.AsyncMock(return_value=[])
        claim.return_value = 9
        yield {
            "open_tables": open_tables,
            "alive": alive,
            "mark": mark,
            "claim": claim,
            "close": os_mod.close,
        }


def finalize(
    collaborators: dict[str, mock.MagicMock],
    root: Path,
    *runs: dict[str, object],
    lock: bool = False,
) -> None:
    for n, _ in enumerate(runs):
        (root / f"a/runs/r{n}").mkdir(parents=True)
        if lock:
            (root / f"a/runs/r{n}/run.lock").write_text("")
    collaborators["open_tables"].return_value.query.return_value = [
        {"folder": f"a/runs/r{n}", "run": json.dumps(run)} for n, run in enumerate(runs)
    ]
    asyncio.run(finalize_lost_runs(mock.Mock(root=root)))


def test_reads_only_unfinished_runs(collaborators: dict[str, mock.MagicMock]) -> None:
    config = mock.Mock()

    asyncio.run(finalize_lost_runs(config))

    collaborators["open_tables"].assert_called_once_with(config)
    collaborators["open_tables"].return_value.query.assert_awaited_once_with(
        "SELECT folder, run FROM runs WHERE unfinished"
    )
    collaborators["mark"].assert_not_called()


def test_ends_a_run_whose_process_is_gone(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    collaborators["alive"].return_value = False

    finalize(collaborators, tmp_path, {**GOING, "pid": 7, "pid_created": 12.5})

    collaborators["alive"].assert_called_once_with(7, 12.5)
    collaborators["claim"].assert_not_called()
    collaborators["mark"].assert_called_once_with(tmp_path / "a/runs/r0")


def test_leaves_a_run_whose_process_still_runs(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    collaborators["alive"].return_value = True

    finalize(collaborators, tmp_path, {**GOING, "pid": 7, "pid_created": 12})

    collaborators["alive"].assert_called_once_with(7, 12)
    collaborators["mark"].assert_not_called()


@pytest.mark.parametrize("created", [{}, {"pid_created": None}, {"pid_created": "x"}])
def test_checks_a_pid_without_a_usable_start_time(
    collaborators: dict[str, mock.MagicMock],
    tmp_path: Path,
    created: dict[str, object],
) -> None:
    collaborators["alive"].return_value = True

    finalize(collaborators, tmp_path, {**GOING, "pid": 7, **created})

    collaborators["alive"].assert_called_once_with(7, None)


@pytest.mark.parametrize("pid", [{}, {"pid": None}, {"pid": "7"}])
def test_ends_a_run_that_never_launched(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path, pid: dict[str, object]
) -> None:
    finalize(collaborators, tmp_path, {**GOING, **pid})

    collaborators["alive"].assert_not_called()
    collaborators["mark"].assert_called_once_with(tmp_path / "a/runs/r0")


def test_skips_a_locked_run(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    collaborators["claim"].return_value = None

    finalize(collaborators, tmp_path, GOING, lock=True)

    collaborators["claim"].assert_called_once_with(tmp_path / "a/runs/r0")
    collaborators["alive"].assert_not_called()
    collaborators["mark"].assert_not_called()
    collaborators["close"].assert_not_called()


def test_marks_an_unlocked_run_lost_and_releases_the_lock(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    finalize(collaborators, tmp_path, {**GOING, "pid": 7}, lock=True)

    collaborators["alive"].assert_not_called()
    collaborators["mark"].assert_called_once_with(tmp_path / "a/runs/r0")
    collaborators["close"].assert_called_once_with(9)


def test_closes_the_lock_even_if_marking_raises(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    collaborators["mark"].side_effect = OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        finalize(collaborators, tmp_path, GOING, lock=True)

    collaborators["close"].assert_called_once_with(9)


def test_continues_after_a_locked_run_to_finalize_a_later_lost_run(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    (tmp_path / "a/runs/r0").mkdir(parents=True)
    (tmp_path / "a/runs/r0/run.lock").write_text("")
    (tmp_path / "a/runs/r1").mkdir(parents=True)
    collaborators["claim"].return_value = None
    collaborators["open_tables"].return_value.query.return_value = [
        {"folder": "a/runs/r0", "run": json.dumps(GOING)},
        {"folder": "a/runs/r1", "run": json.dumps(GOING)},
    ]

    asyncio.run(finalize_lost_runs(mock.Mock(root=tmp_path)))

    collaborators["mark"].assert_called_once_with(tmp_path / "a/runs/r1")
