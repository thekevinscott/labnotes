import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


def untracked_diff(repo_root: Path) -> bytes:
    """Patch adding every untracked, non-ignored file, as the snapshot copies them."""
    listing = subprocess.check_output(
        ["git", "ls-files", "-o", "--exclude-standard", "-z"],
        cwd=repo_root,
        stderr=subprocess.DEVNULL,
    )
    # A trailing slash marks an untracked nested repository, which git cannot add.
    paths = [path for path in listing.split(b"\0") if path and not path.endswith(b"/")]
    if not paths:
        return b""
    with TemporaryDirectory(prefix="labnotes-index-") as directory:
        # A throwaway index keeps the user's real index untouched.
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(directory) / "index")}
        subprocess.run(
            ["git", "add", "--intent-to-add", "--pathspec-from-file=-"]
            + ["--pathspec-file-nul"],
            cwd=repo_root,
            env=env,
            input=b"\0".join(paths),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        # Files over 1 MiB show as binary so stray data cannot bloat every patch.
        return subprocess.run(
            ["git", "-c", "core.bigFileThreshold=1m", "diff"],
            cwd=repo_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        ).stdout
