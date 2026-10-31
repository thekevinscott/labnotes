import logging
import signal
import shutil
import subprocess
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory


@dataclass(frozen=True)
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
        diff = git(root, "diff", "HEAD")
    except (OSError, subprocess.SubprocessError):
        logging.warning("Project has no readable Git HEAD; running from the live tree")
        yield ProjectSnapshot(root)
        return
    files = git(root, "ls-files", "-co", "--exclude-standard", "-z").split(b"\0")
    ignored = git(
        root, "ls-files", "-oi", "--exclude-standard", "--directory", "-z"
    ).split(b"\0")
    base = Path("/tmp/labnotes")
    base.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=base) as directory:
        snapshot = Path(directory)
        previous = (
            {
                number: signal.getsignal(number)
                for number in (signal.SIGTERM, signal.SIGHUP)
            }
            if threading.current_thread() is threading.main_thread()
            else {}
        )

        def stop(_number: int, _frame: object) -> None:
            raise KeyboardInterrupt

        try:
            for number in previous:
                signal.signal(number, stop)
            for raw in files:
                if not raw:
                    continue
                relative = Path(raw.decode())
                source = root / relative
                if not source.exists() and not source.is_symlink():
                    continue
                target = snapshot / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(source, target)
                else:
                    shutil.copy2(source, target)
            for raw in ignored:
                if not raw:
                    continue
                relative = Path(raw.decode().rstrip("/"))
                target = snapshot / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(
                    root / relative, target_is_directory=(root / relative).is_dir()
                )
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)
        yield ProjectSnapshot(snapshot, sha, diff)
