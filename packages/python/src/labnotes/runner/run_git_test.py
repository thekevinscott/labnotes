from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.run_git import run_git

COMMIT = "0123456789abcdef0123456789abcdef01234567"


class GitError(Exception):
    pass


@pytest.fixture
def process() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.runner.run_git.subprocess") as process:
        process.DEVNULL = -3
        process.SubprocessError = GitError
        yield process


@pytest.mark.parametrize("status,dirty", [(b"", False), (b" M tracked\n", True)])
def test_reads_head_and_tracked_status_from_the_command_root(
    tmp_path: Path, process: mock.MagicMock, status: bytes, dirty: bool
) -> None:
    process.check_output.side_effect = [f"{COMMIT}\n".encode(), status]

    assert run_git(tmp_path) == {"commit": COMMIT, "dirty": dirty}

    assert process.check_output.call_args_list == [
        mock.call(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_path,
            stderr=-3,
            timeout=3,
        ),
        mock.call(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=tmp_path,
            stderr=-3,
            timeout=3,
        ),
    ]


@pytest.mark.parametrize("after_head", [False, True])
@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("git"),
        GitError("failed or timed out"),
    ],
)
def test_failed_lookup_returns_none(
    tmp_path: Path, process: mock.MagicMock, after_head: bool, error: Exception
) -> None:
    process.check_output.side_effect = (
        [COMMIT.encode(), error] if after_head else [error]
    )

    assert run_git(tmp_path) is None


def test_unreadable_commit_returns_none(
    tmp_path: Path, process: mock.MagicMock
) -> None:
    process.check_output.side_effect = [b"\xff", b""]

    assert run_git(tmp_path) is None
