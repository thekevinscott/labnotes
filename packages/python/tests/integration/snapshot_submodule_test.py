import subprocess
from pathlib import Path

from labnotes.runner.project_snapshot import project_snapshot


def _commit(root: Path) -> None:
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "initial",
        ],
        cwd=root,
        check=True,
    )


def test_snapshot_submodule_has_working_git_metadata(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    (source / "version.txt").write_text("v1\n")
    _commit(source)
    submodule_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source)

    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(source),
            "dependency",
        ],
        cwd=project,
        check=True,
    )
    _commit(project)
    (project / "dependency/version.txt").write_text("dirty\n")

    with project_snapshot(project) as snapshot:
        dependency = snapshot.root / "dependency"
        assert (dependency / "version.txt").read_text() == "dirty\n"
        assert (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=dependency)
            == submodule_sha
        )
        assert b" M version.txt" in subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=dependency
        )
        assert snapshot.diff is not None
        assert (
            b"diff --git a/dependency/version.txt b/dependency/version.txt"
            in snapshot.diff
        )
        assert b"+dirty" in snapshot.diff
