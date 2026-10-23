import asyncio
import json
import os
from pathlib import Path
from unittest import mock

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


def test_samples_a_running_runs_tree_and_sizes_its_folder(tmp_path: Path) -> None:
    make_run(tmp_path, pid=os.getpid())
    shown = len(json.dumps({"pid": os.getpid()})) + 5000

    with mock.patch("labnotes.utils.run_usage.tree_rss", return_value=123) as tree_rss:
        assert usage(tmp_path, running=True) == {"memory": 123, "size": shown}
    tree_rss.assert_called_once_with(os.getpid())


def test_sizes_a_finished_run_without_sampling(tmp_path: Path) -> None:
    make_run(tmp_path, pid=os.getpid())

    with mock.patch("labnotes.utils.run_usage.tree_rss") as tree_rss:
        found = usage(tmp_path, running=False)
    tree_rss.assert_not_called()
    assert found["memory"] is None
    assert found["size"] is not None
    assert found["size"] > 5000


def test_has_no_memory_before_the_pid_is_recorded(tmp_path: Path) -> None:
    make_run(tmp_path)

    with mock.patch("labnotes.utils.run_usage.tree_rss") as tree_rss:
        assert usage(tmp_path, running=True)["memory"] is None
    tree_rss.assert_not_called()


def test_tolerates_a_half_written_run_json(tmp_path: Path) -> None:
    make_run(tmp_path)
    (tmp_path / "run.json").write_text('{"pid": ')

    assert usage(tmp_path, running=True)["memory"] is None


def test_has_nothing_for_a_missing_folder(tmp_path: Path) -> None:
    assert usage(tmp_path / "gone", running=True) == {"memory": None, "size": None}
