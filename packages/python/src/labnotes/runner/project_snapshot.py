import logging
import os
import signal
import shutil
import subprocess
from contextlib import contextmanager
from collections.abc import Callable
from dataclasses import dataclass
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from types import FrameType

from labnotes.runner.untracked_diff import untracked_diff


@dataclass
class ProjectSnapshot:
    root: Path
    sha: str | None = None
    diff: bytes | None = None


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL)


@contextmanager
def project_snapshot(root: Path) -> Iterator[ProjectSnapshot]:
    """Capture the working tree once for all commands in an invocation."""
    try:
        git(root, "rev-parse", "--is-inside-work-tree")
    except (OSError, subprocess.SubprocessError):
        logging.warning("Project is not a git repository; running from the live tree")
        yield ProjectSnapshot(root)
        return

    try:
        sha = git(root, "rev-parse", "HEAD").decode("ascii").strip()
        repo_root = Path(git(root, "rev-parse", "--show-toplevel").decode().strip())
        project_prefix = root.resolve().relative_to(repo_root.resolve())
        diff = git(repo_root, "diff", "HEAD") + untracked_diff(repo_root)
    except (OSError, subprocess.SubprocessError):
        logging.warning("Project has no readable Git HEAD; running from the live tree")
        yield ProjectSnapshot(root)
        return
    files = filter(
        None, git(repo_root, "ls-files", "-co", "--exclude-standard", "-z").split(b"\0")
    )
    ignored = filter(
        None,
        git(
            repo_root, "ls-files", "-oi", "--exclude-standard", "--directory", "-z"
        ).split(b"\0"),
    )
    with TemporaryDirectory(prefix="labnotes-") as directory:
        snapshot = Path(directory)
        previous: dict[
            signal.Signals,
            Callable[[int, FrameType | None], object] | int | signal.Handlers | None,
        ] = {}

        def stop(_number: int, _frame: object) -> None:
            raise KeyboardInterrupt

        try:
            for number in (signal.SIGTERM, signal.SIGHUP):
                try:
                    old_handler = signal.signal(number, stop)
                except ValueError:
                    break  # Signals can only be installed from the main thread.
                previous[number] = old_handler
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--quiet",
                    "--shared",
                    "--no-checkout",
                    str(repo_root),
                    str(snapshot),
                ],
                check=True,
            )
            for raw in files:
                relative = Path(raw.decode())
                source = repo_root / relative
                if not source.exists() and not source.is_symlink():
                    continue
                target = snapshot / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.is_symlink():
                    target.symlink_to(
                        os.readlink(source), target_is_directory=source.is_dir()
                    )
                elif source.is_dir() and (source / ".git").is_file():
                    subprocess.run(
                        [
                            "git",
                            "clone",
                            "--quiet",
                            "--shared",
                            "--no-checkout",
                            str(source),
                            str(target),
                        ],
                        check=True,
                    )
                    shutil.copytree(
                        source,
                        target,
                        symlinks=True,
                        dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git"),
                    )
                    submodule_sha = (
                        git(source, "rev-parse", "HEAD").decode("ascii").strip()
                    )
                    subprocess.run(
                        ["git", "-C", str(target), "reset", "--quiet", submodule_sha],
                        check=True,
                    )
                elif source.is_dir():
                    shutil.copytree(source, target, symlinks=True)
                else:
                    shutil.copy2(source, target)
            skipped: set[Path] = set()
            for raw in ignored:
                relative = Path(raw.decode().rstrip("/"))
                if any(parent in relative.parents for parent in skipped):
                    continue
                if any((snapshot / parent).is_symlink() for parent in relative.parents):
                    continue
                source = repo_root / relative
                if source.is_dir() and (source / "pyvenv.cfg").exists():
                    skipped.add(relative)
                    continue
                target = snapshot / relative
                if target.is_symlink() or target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(source, target_is_directory=source.is_dir())
            subprocess.run(
                ["git", "-C", str(snapshot), "reset", "--quiet", sha], check=True
            )
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)
        yield ProjectSnapshot(snapshot / project_prefix, sha, diff)
