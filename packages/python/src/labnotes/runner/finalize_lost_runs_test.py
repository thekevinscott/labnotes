import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.finalize_lost_runs import finalize_lost_runs

GOING: dict[str, object] = {
    "params": {"n": 1},
    "ended": None,
    "exit_code": None,
    "error": None,
}
DONE: dict[str, object] = {**GOING, "ended": "2026-01-01T00:00:00Z", "exit_code": 0}
LOST = {"ended": "1970-01-01T00:01:40Z", "ended_by": "lost"}


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.runner.finalize_lost_runs.open_tables") as open_tables,
        mock.patch("labnotes.runner.finalize_lost_runs.process_alive") as alive,
        mock.patch("labnotes.runner.finalize_lost_runs.write_run_json") as write,
        mock.patch("labnotes.runner.finalize_lost_runs.claim_run") as claim,
        mock.patch("labnotes.runner.finalize_lost_runs.os.close") as close,
        mock.patch("labnotes.runner.finalize_lost_runs.time") as time,
        mock.patch("labnotes.runner.finalize_lost_runs.UNFINISHED", "unfinished"),
    ):
        time.time.return_value = 100
        open_tables.return_value.query = mock.AsyncMock(return_value=[])
        claim.return_value = 9
        yield {
            "open_tables": open_tables,
            "alive": alive,
            "write": write,
            "claim": claim,
            "close": close,
        }


def finalize(
    collaborators: dict[str, mock.MagicMock],
    root: Path,
    scanned: dict[str, object],
    on_disk: object = None,
    *,
    lock: bool = False,
) -> Path:
    folder = root / "a/runs/r0"
    folder.mkdir(parents=True)
    disk = scanned if on_disk is None else on_disk
    text = disk if isinstance(disk, str) else json.dumps(disk)
    (folder / "run.json").write_text(text, encoding="utf-8")
    if lock:
        (folder / "run.lock").write_text("")
    collaborators["open_tables"].return_value.query.return_value = [
        {"folder": "a/runs/r0", "run": json.dumps(scanned)}
    ]
    asyncio.run(finalize_lost_runs(mock.Mock(root=root)))
    return folder


def test_reads_only_unfinished_runs(collaborators: dict[str, mock.MagicMock]) -> None:
    config = mock.Mock()

    asyncio.run(finalize_lost_runs(config))

    collaborators["open_tables"].assert_called_once_with(config)
    collaborators["open_tables"].return_value.query.assert_awaited_once_with(
        "SELECT folder, run FROM runs WHERE unfinished"
    )
    collaborators["write"].assert_not_called()


def test_ends_a_run_whose_process_is_gone(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    collaborators["alive"].return_value = False
    run: dict[str, object] = {**GOING, "pid": 7, "pid_created": 12.5, "note": "kept"}

    folder = finalize(collaborators, tmp_path, run)

    collaborators["alive"].assert_called_once_with(7, 12.5)
    collaborators["claim"].assert_not_called()
    collaborators["write"].assert_called_once_with(folder, {**run, **LOST})


def test_leaves_a_run_whose_process_still_runs(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    collaborators["alive"].return_value = True

    finalize(collaborators, tmp_path, {**GOING, "pid": 7, "pid_created": 12})

    collaborators["alive"].assert_called_once_with(7, 12)
    collaborators["write"].assert_not_called()


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
    run = {**GOING, **pid}

    folder = finalize(collaborators, tmp_path, run)

    collaborators["alive"].assert_not_called()
    collaborators["write"].assert_called_once_with(folder, {**run, **LOST})


def test_skips_a_locked_run(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    collaborators["claim"].return_value = None

    folder = finalize(collaborators, tmp_path, GOING, lock=True)

    collaborators["claim"].assert_called_once_with(folder)
    collaborators["alive"].assert_not_called()
    collaborators["write"].assert_not_called()
    collaborators["close"].assert_not_called()


def test_marks_an_unlocked_run_lost_from_disk_not_from_the_scanned_row(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    on_disk = {**GOING, "note": "newer"}

    folder = finalize(collaborators, tmp_path, GOING, on_disk, lock=True)

    collaborators["alive"].assert_not_called()
    collaborators["write"].assert_called_once_with(folder, {**on_disk, **LOST})
    collaborators["close"].assert_called_once_with(9)


def test_leaves_a_run_that_finished_after_the_scan(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    finalize(collaborators, tmp_path, GOING, DONE, lock=True)

    collaborators["write"].assert_not_called()
    collaborators["close"].assert_called_once_with(9)


def test_leaves_a_run_with_an_exit_code_but_no_end(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    finalize(collaborators, tmp_path, GOING, {**GOING, "exit_code": 1}, lock=True)

    collaborators["write"].assert_not_called()


@pytest.mark.parametrize("disk", ["{not json", "[]"])
def test_leaves_an_unreadable_run_json(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path, disk: str
) -> None:
    finalize(collaborators, tmp_path, GOING, disk, lock=True)

    collaborators["write"].assert_not_called()
    collaborators["close"].assert_called_once_with(9)


def test_leaves_a_run_whose_run_json_is_missing(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    (tmp_path / "a/runs/r0").mkdir(parents=True)
    (tmp_path / "a/runs/r0/run.lock").write_text("")
    collaborators["open_tables"].return_value.query.return_value = [
        {"folder": "a/runs/r0", "run": json.dumps(GOING)}
    ]

    asyncio.run(finalize_lost_runs(mock.Mock(root=tmp_path)))

    collaborators["write"].assert_not_called()


def test_closes_the_lock_even_if_the_write_raises(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    collaborators["write"].side_effect = OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        finalize(collaborators, tmp_path, GOING, lock=True)

    collaborators["close"].assert_called_once_with(9)


def test_marks_only_the_last_of_several_invocations_lost(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    run: dict[str, object] = {
        **GOING,
        "invocations": [
            {"exit_code": 1},
            {"exit_code": 2},
            {"started": "s", "ended": None},
        ],
    }

    folder = finalize(collaborators, tmp_path, run, lock=True)

    collaborators["write"].assert_called_once_with(
        folder,
        {
            **run,
            **LOST,
            "invocations": [
                {"exit_code": 1},
                {"exit_code": 2},
                {"started": "s", **LOST},
            ],
        },
    )


def test_continues_after_a_locked_run_to_finalize_a_later_lost_run(
    collaborators: dict[str, mock.MagicMock], tmp_path: Path
) -> None:
    for name in ("r0", "r1"):
        folder = tmp_path / "a/runs" / name
        folder.mkdir(parents=True)
        (folder / "run.json").write_text(json.dumps(GOING), encoding="utf-8")
    (tmp_path / "a/runs/r0/run.lock").write_text("")
    collaborators["claim"].return_value = None
    collaborators["open_tables"].return_value.query.return_value = [
        {"folder": "a/runs/r0", "run": json.dumps(GOING)},
        {"folder": "a/runs/r1", "run": json.dumps(GOING)},
    ]

    asyncio.run(finalize_lost_runs(mock.Mock(root=tmp_path)))

    collaborators["write"].assert_called_once_with(
        tmp_path / "a/runs/r1", {**GOING, **LOST}
    )
