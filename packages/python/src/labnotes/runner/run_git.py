import subprocess
from pathlib import Path


def run_git(root: Path) -> dict[str, str | bool] | None:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        status = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        return {"commit": commit.decode("ascii").strip(), "dirty": bool(status)}
    except (OSError, subprocess.SubprocessError, UnicodeError):
        # Git metadata is optional; a failed lookup must not prevent the run.
        return None
