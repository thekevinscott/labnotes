from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
from unittest import mock

import pytest

from labnotes.runner.project_snapshot import project_snapshot


def test_copies_code_links_ignored_paths_and_removes_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "src/code.py").write_text("original")
    (root / "data").mkdir()
    (root / "data/input").write_text("live")
    commands = [
        b"true\n",
        b"abc\n",
        str(root).encode(),
        b"diff",
        b"src/code.py\0",
        b"data/\0",
    ]
    with (
        mock.patch("labnotes.runner.project_snapshot.git", side_effect=commands) as git,
        mock.patch("labnotes.runner.project_snapshot.subprocess.run"),
    ):
        with project_snapshot(root) as snapshot:
            assert snapshot.root != root
            assert (snapshot.root / "src/code.py").read_text() == "original"
            assert (snapshot.root / "data").is_symlink()
            assert (snapshot.root / "data/input").read_text() == "live"
            assert (snapshot.sha, snapshot.diff) == ("abc", b"diff")
            location = snapshot.root
        assert not location.exists()
    assert git.call_count == 6


def test_uses_live_tree_when_git_is_unavailable(tmp_path: Path) -> None:
    with mock.patch(
        "labnotes.runner.project_snapshot.git",
        side_effect=OSError("git unavailable"),
    ):
        with project_snapshot(tmp_path) as snapshot:
            assert snapshot.root == tmp_path
            assert snapshot.sha is None


def test_uses_live_tree_when_git_has_no_head(tmp_path: Path) -> None:
    with mock.patch(
        "labnotes.runner.project_snapshot.git",
        side_effect=[b"true\n", OSError("no HEAD")],
    ):
        with project_snapshot(tmp_path) as snapshot:
            assert snapshot.root == tmp_path
            assert snapshot.sha is None


def test_git_command_reads_bytes_from_project_root(tmp_path: Path) -> None:
    from labnotes.runner.project_snapshot import git

    with mock.patch(
        "labnotes.runner.project_snapshot.subprocess.check_output", return_value=b"ok"
    ) as output:
        assert git(tmp_path, "rev-parse", "HEAD") == b"ok"
    output.assert_called_once_with(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, stderr=mock.ANY
    )


def test_skips_missing_files_and_preserves_directory_symlink(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "real").mkdir()
    (root / "real/code.py").write_text("original")
    (root / "link").symlink_to(root / "real", target_is_directory=True)
    commands = [
        b"true\n",
        b"abc\n",
        str(root).encode(),
        b"",
        b"missing.py\0link\0",
        b"",
    ]
    with (
        mock.patch("labnotes.runner.project_snapshot.git", side_effect=commands),
        mock.patch("labnotes.runner.project_snapshot.subprocess.run"),
    ):
        with project_snapshot(root) as snapshot:
            assert not (snapshot.root / "missing.py").exists()
            assert (snapshot.root / "link/code.py").read_text() == "original"
            assert (snapshot.root / "link").is_symlink()


def test_interrupt_during_copy_removes_partial_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    commands = [b"true\n", b"abc\n", str(root).encode(), b"", b"", b""]
    base = tmp_path
    before = set(base.iterdir())
    called = False

    def interrupt(_number: int, handler: object) -> None:
        nonlocal called
        if not called:
            called = True
            handler(15, None)  # type: ignore[operator]

    with (
        mock.patch("labnotes.runner.project_snapshot.git", side_effect=commands),
        mock.patch("labnotes.runner.project_snapshot.subprocess.run"),
        mock.patch(
            "labnotes.runner.project_snapshot.TemporaryDirectory",
            side_effect=lambda **_kwargs: tempfile.TemporaryDirectory(dir=base),
        ),
        mock.patch(
            "labnotes.runner.project_snapshot.signal.signal", side_effect=interrupt
        ),
        pytest.raises(KeyboardInterrupt),
    ):
        with project_snapshot(root):
            pass
    assert set(base.iterdir()) == before


def test_snapshot_can_be_created_from_another_thread(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    commands = [b"true\n", b"abc\n", str(root).encode(), b"", b"", b""]

    def take_snapshot() -> bool:
        with project_snapshot(root) as snapshot:
            return snapshot.root.exists()

    with (
        mock.patch("labnotes.runner.project_snapshot.git", side_effect=commands),
        mock.patch("labnotes.runner.project_snapshot.subprocess.run"),
    ):
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(take_snapshot).result()


def test_copies_deeply_nested_untracked_file(tmp_path: Path) -> None:
    root = tmp_path / "project"
    source = root / "one/two/three/code.py"
    source.parent.mkdir(parents=True)
    source.write_text("nested")
    commands = [
        b"true\n",
        b"abc\n",
        str(root).encode(),
        b"",
        b"one/two/three/code.py\0",
        b"",
    ]
    with (
        mock.patch("labnotes.runner.project_snapshot.git", side_effect=commands),
        mock.patch("labnotes.runner.project_snapshot.subprocess.run"),
    ):
        with project_snapshot(root) as snapshot:
            assert (snapshot.root / "one/two/three/code.py").read_text() == "nested"


def test_links_deeply_nested_ignored_path(tmp_path: Path) -> None:
    root = tmp_path / "project"
    source = root / "one/two/three/data"
    source.mkdir(parents=True)
    commands = [
        b"true\n",
        b"abc\n",
        str(root).encode(),
        b"",
        b"",
        b"one/two/three/data/\0",
    ]
    with (
        mock.patch("labnotes.runner.project_snapshot.git", side_effect=commands),
        mock.patch("labnotes.runner.project_snapshot.subprocess.run"),
    ):
        with project_snapshot(root) as snapshot:
            assert (snapshot.root / "one/two/three/data").is_symlink()


def test_restores_signal_handlers_after_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    commands = [b"true\n", b"abc\n", str(root).encode(), b"", b"", b""]
    old_term = mock.Mock()
    old_hup = mock.Mock()
    with (
        mock.patch("labnotes.runner.project_snapshot.git", side_effect=commands),
        mock.patch("labnotes.runner.project_snapshot.subprocess.run"),
        mock.patch(
            "labnotes.runner.project_snapshot.signal.signal",
            side_effect=[old_term, old_hup, None, None],
        ) as change_handler,
    ):
        with project_snapshot(root):
            pass
    assert change_handler.call_count == 4
    assert change_handler.call_args_list[2].args == (
        change_handler.call_args_list[0].args[0],
        old_term,
    )
    assert change_handler.call_args_list[3].args == (
        change_handler.call_args_list[1].args[0],
        old_hup,
    )


def test_copies_tracked_directory_without_following_its_symlinks(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    (root / "folder").mkdir(parents=True)
    (root / "folder/link").symlink_to("missing-target")
    commands = [b"true\n", b"abc\n", str(root).encode(), b"", b"folder\0", b""]
    with (
        mock.patch("labnotes.runner.project_snapshot.git", side_effect=commands),
        mock.patch("labnotes.runner.project_snapshot.subprocess.run"),
    ):
        with project_snapshot(root) as snapshot:
            assert (snapshot.root / "folder/link").is_symlink()
            assert (snapshot.root / "folder/link").readlink() == Path("missing-target")


def test_submodule_gets_its_own_git_directory(tmp_path: Path) -> None:
    root = tmp_path / "project"
    dependency = root / "dependency"
    dependency.mkdir(parents=True)
    (dependency / ".git").write_text("gitdir: ../.git/modules/dependency\n")
    (dependency / "code.py").write_text("dirty")
    commands = [b"true\n", b"abc\n", b"", b"dependency\0", b"", b"def\n"]

    def clone(args: list[str], **_kwargs: object) -> None:
        if args[:2] == ["git", "clone"]:
            target = Path(args[-1])
            target.mkdir(exist_ok=True)
            (target / ".git").mkdir(exist_ok=True)

    with (
        mock.patch("labnotes.runner.project_snapshot.git", side_effect=commands),
        mock.patch(
            "labnotes.runner.project_snapshot.subprocess.run", side_effect=clone
        ) as run,
    ):
        with project_snapshot(root) as snapshot:
            assert (snapshot.root / "dependency/.git").is_dir()
            assert (snapshot.root / "dependency/code.py").read_text() == "dirty"
    assert run.call_args_list[2].args[0][-2:] == ["--quiet", "def"]


def test_skips_virtualenv_and_its_ignored_entries(tmp_path: Path) -> None:
    root = tmp_path / "project"
    venv = root / ".venv"
    venv.mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\n")
    (venv / ".gitignore").write_text("*\n")
    (root / "later").mkdir()
    commands = [
        b"true\n",
        b"abc\n",
        str(root).encode(),
        b"",
        b"",
        b".venv/\0.venv/.gitignore\0later/\0",
    ]
    with (
        mock.patch("labnotes.runner.project_snapshot.git", side_effect=commands),
        mock.patch("labnotes.runner.project_snapshot.subprocess.run"),
    ):
        with project_snapshot(root) as snapshot:
            assert not (snapshot.root / ".venv").exists()
            assert not (snapshot.root / ".venv").is_symlink()
            assert (snapshot.root / "later").is_symlink()


def test_skips_entries_under_linked_ignored_directory(tmp_path: Path) -> None:
    root = tmp_path / "project"
    data = root / "data"
    data.mkdir(parents=True)
    (data / "child").write_text("live")
    (root / "later").mkdir()
    commands = [
        b"true\n",
        b"abc\n",
        str(root).encode(),
        b"",
        b"",
        b"data/\0data/child\0later/\0",
    ]
    with (
        mock.patch("labnotes.runner.project_snapshot.git", side_effect=commands),
        mock.patch("labnotes.runner.project_snapshot.subprocess.run"),
    ):
        with project_snapshot(root) as snapshot:
            assert (snapshot.root / "data").is_symlink()
            assert (data / "child").read_text() == "live"
            assert (snapshot.root / "later").is_symlink()


def test_skips_ignored_path_already_copied(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "same.txt").write_text("copied")
    (root / "later").mkdir()
    commands = [
        b"true\n",
        b"abc\n",
        str(root).encode(),
        b"",
        b"same.txt\0",
        b"same.txt\0later/\0",
    ]
    with (
        mock.patch("labnotes.runner.project_snapshot.git", side_effect=commands),
        mock.patch("labnotes.runner.project_snapshot.subprocess.run"),
    ):
        with project_snapshot(root) as snapshot:
            assert (snapshot.root / "same.txt").read_text() == "copied"
            assert not (snapshot.root / "same.txt").is_symlink()
            assert (snapshot.root / "later").is_symlink()


def test_clone_and_reset_check_for_git_errors(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    commands = [b"true\n", b"abc\n", str(root).encode(), b"", b"", b""]
    with (
        mock.patch("labnotes.runner.project_snapshot.git", side_effect=commands),
        mock.patch("labnotes.runner.project_snapshot.subprocess.run") as run,
    ):
        with project_snapshot(root):
            pass
    assert [call.kwargs["check"] for call in run.call_args_list] == [True, True]


def test_non_main_thread_stops_installing_signal_handlers(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    commands = [b"true\n", b"abc\n", str(root).encode(), b"", b"", b""]
    with (
        mock.patch("labnotes.runner.project_snapshot.git", side_effect=commands),
        mock.patch("labnotes.runner.project_snapshot.subprocess.run"),
        mock.patch(
            "labnotes.runner.project_snapshot.signal.signal", side_effect=ValueError
        ) as change_handler,
    ):
        with project_snapshot(root):
            pass
    change_handler.assert_called_once()
