import asyncio
import json
import os
from pathlib import Path
from unittest import mock

import pytest

from labnotes.utils.run_usage import run_usage


def usage(folder: Path, running: bool) -> dict[str, int | None]:
    return asyncio.run(run_usage(folder, running))


def make_run(folder: Path, **run: object) -> None:
    (folder / "nested").mkdir(parents=True)
    (folder / "run.json").write_text(json.dumps(run))
    (folder / "nested" / "out.bin").write_bytes(b"x" * 5000)
    # Inside a git repo that ignores the whole folder.
    (folder / ".git").mkdir()
    (folder / ".gitignore").write_text("*\n")


GOING = {"ended": None, "exit_code": None, "error": None}


def test_samples_a_running_runs_tree_and_sizes_its_folder(tmp_path: Path) -> None:
    run = {**GOING, "pid": os.getpid(), "pid_created": 12.5}
    make_run(tmp_path, **run)
    shown = len(json.dumps(run)) + 5000

    with mock.patch("labnotes.utils.run_usage.tree_rss", return_value=123) as tree_rss:
        assert usage(tmp_path, running=True) == {"memory": 123, "size": shown}
    tree_rss.assert_called_once_with(os.getpid(), 12.5)


@pytest.mark.parametrize("ended", [{"ended": "now"}, {"exit_code": 0}, {"error": "x"}])
def test_does_not_sample_a_run_its_record_says_has_ended(
    tmp_path: Path, ended: dict[str, object]
) -> None:
    make_run(tmp_path, **{**GOING, "pid": 7, "pid_created": 12.5, **ended})

    with mock.patch("labnotes.utils.run_usage.tree_rss") as tree_rss:
        assert usage(tmp_path, running=True)["memory"] is None
    tree_rss.assert_not_called()


def test_does_not_sample_a_pid_without_its_start_time(tmp_path: Path) -> None:
    make_run(tmp_path, **GOING, pid=7)

    with mock.patch("labnotes.utils.run_usage.tree_rss") as tree_rss:
        assert usage(tmp_path, running=True)["memory"] is None
    tree_rss.assert_not_called()


def test_sizes_a_finished_run_without_sampling(tmp_path: Path) -> None:
    make_run(tmp_path, **GOING, pid=7, pid_created=12.5)

    with mock.patch("labnotes.utils.run_usage.tree_rss") as tree_rss:
        found = usage(tmp_path, running=False)
    tree_rss.assert_not_called()
    assert found["memory"] is None
    assert found["size"] is not None
    assert found["size"] > 5000


def test_has_no_memory_before_the_pid_is_recorded(tmp_path: Path) -> None:
    make_run(tmp_path, **GOING)

    with mock.patch("labnotes.utils.run_usage.tree_rss") as tree_rss:
        assert usage(tmp_path, running=True)["memory"] is None
    tree_rss.assert_not_called()


def test_tolerates_a_half_written_run_json(tmp_path: Path) -> None:
    make_run(tmp_path)
    (tmp_path / "run.json").write_text('{"pid": ')

    assert usage(tmp_path, running=True)["memory"] is None


def test_has_nothing_for_a_missing_folder(tmp_path: Path) -> None:
    assert usage(tmp_path / "gone", running=True) == {"memory": None, "size": None}


def test_leaves_out_hidden_files_and_folders(tmp_path: Path) -> None:
    make_run(tmp_path)
    before = usage(tmp_path, running=False)["size"]
    (tmp_path / ".hidden").write_bytes(b"x" * 3000)
    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache" / "blob").write_bytes(b"x" * 3000)

    assert usage(tmp_path, running=False)["size"] == before


def test_counts_a_file_symlink_as_its_target(tmp_path: Path) -> None:
    folder = tmp_path / "run"
    make_run(folder)
    before = usage(folder, running=False)["size"]
    (tmp_path / "outside.bin").write_bytes(b"x" * 40_000)
    (folder / "link.bin").symlink_to(tmp_path / "outside.bin")

    assert usage(folder, running=False)["size"] == before + 40_000  # type: ignore[operator]
