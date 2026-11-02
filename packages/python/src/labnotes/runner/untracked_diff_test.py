import subprocess
from pathlib import Path

import pytest

from labnotes.runner.untracked_diff import untracked_diff


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def test_adds_untracked_text_file_as_new_file(repo: Path) -> None:
    (repo / "new.py").write_text("print('hi')\n")
    patch = untracked_diff(repo).decode()
    assert patch.startswith("diff --git a/new.py b/new.py\nnew file mode 100644\n")
    assert patch.endswith("--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+print('hi')\n")


def test_patch_applies_to_recreate_untracked_files(
    repo: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    (repo / "dir").mkdir()
    (repo / "dir/a.txt").write_text("a\n")
    (repo / "b.txt").write_text("b\n")
    target = tmp_path_factory.mktemp("target")
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    subprocess.run(["git", "apply"], cwd=target, input=untracked_diff(repo), check=True)
    assert (target / "dir/a.txt").read_text() == "a\n"
    assert (target / "b.txt").read_text() == "b\n"


def test_leaves_out_ignored_and_tracked_files(repo: Path) -> None:
    (repo / ".gitignore").write_text("ignored.txt\n")
    (repo / "ignored.txt").write_text("secret\n")
    (repo / "tracked.txt").write_text("tracked\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    patch = untracked_diff(repo).decode()
    assert "b/.gitignore" in patch
    assert "b/ignored.txt" not in patch
    assert "b/tracked.txt" not in patch


def test_binary_file_is_named_without_its_bytes(repo: Path) -> None:
    (repo / "weights.bin").write_bytes(b"\0secret-bytes")
    patch = untracked_diff(repo)
    assert b"Binary files /dev/null and b/weights.bin differ" in patch
    assert b"secret-bytes" not in patch


def test_text_file_over_one_mebibyte_is_named_without_its_contents(repo: Path) -> None:
    (repo / "data.csv").write_text("row\n" * 300_000)
    (repo / "small.csv").write_text("row\n" * 50_000)
    patch = untracked_diff(repo)
    assert b"Binary files /dev/null and b/data.csv differ" in patch
    assert b"+++ b/small.csv" in patch
    assert len(patch) < 300_000


def test_untracked_symlink_records_its_target(repo: Path) -> None:
    (repo / "link").symlink_to("elsewhere")
    patch = untracked_diff(repo).decode()
    assert "new file mode 120000" in patch
    assert "+elsewhere" in patch


def test_skips_untracked_nested_repository(repo: Path) -> None:
    nested = repo / "nested"
    nested.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=nested, check=True)
    (nested / "code.py").write_text("x\n")
    assert untracked_diff(repo) == b""


def test_clean_repository_has_empty_patch(repo: Path) -> None:
    assert untracked_diff(repo) == b""
