from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.untracked_diff import untracked_diff


@pytest.fixture
def git() -> Iterator[mock.Mock]:
    with mock.patch("labnotes.runner.untracked_diff.subprocess") as patched:
        patched.run.side_effect = [mock.Mock(), mock.Mock(stdout=b"patch")]
        yield patched


def test_diffs_listed_files_through_a_throwaway_index(
    git: mock.Mock, tmp_path: Path
) -> None:
    git.check_output.return_value = b"a.py\0nested/\0z.txt\0"

    assert untracked_diff(tmp_path) == b"patch"

    git.check_output.assert_called_once_with(
        ["git", "ls-files", "-o", "--exclude-standard", "-z"],
        cwd=tmp_path,
        stderr=git.DEVNULL,
    )
    add, diff = git.run.call_args_list
    assert add.args[0] == [
        "git",
        "add",
        "--intent-to-add",
        "--pathspec-from-file=-",
        "--pathspec-file-nul",
    ]
    assert add.kwargs["input"] == b"a.py\0z.txt"
    assert add.kwargs["cwd"] == tmp_path
    assert add.kwargs["check"] is True
    assert add.kwargs["stdout"] == add.kwargs["stderr"] == git.DEVNULL
    assert diff.args[0] == ["git", "-c", "core.bigFileThreshold=1m", "diff"]
    assert diff.kwargs["cwd"] == tmp_path
    assert diff.kwargs["check"] is True
    assert diff.kwargs["stdout"] == git.PIPE
    assert diff.kwargs["stderr"] == git.DEVNULL
    index = add.kwargs["env"]["GIT_INDEX_FILE"]
    assert diff.kwargs["env"]["GIT_INDEX_FILE"] == index
    assert Path(index).name == "index"
    assert Path(index).parent.name.startswith("labnotes-index-")
    assert not Path(index).parent.exists()
    assert add.kwargs["env"]["PATH"] == diff.kwargs["env"]["PATH"]


def test_no_untracked_files_runs_no_diff(git: mock.Mock, tmp_path: Path) -> None:
    git.check_output.return_value = b"nested/\0"

    assert untracked_diff(tmp_path) == b""

    git.run.assert_not_called()
