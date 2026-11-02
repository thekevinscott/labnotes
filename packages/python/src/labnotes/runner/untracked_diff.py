import subprocess
from pathlib import Path


def untracked_diff(repo_root: Path) -> bytes:
    """Patch adding every untracked, non-ignored file, as the snapshot copies them."""
    listing = subprocess.check_output(
        ["git", "ls-files", "-o", "--exclude-standard", "-z"],
        cwd=repo_root,
        stderr=subprocess.DEVNULL,
    )
    patch = b""
    for raw in filter(None, listing.split(b"\0")):
        relative = raw.decode()
        path = repo_root / relative
        if path.is_dir() and not path.is_symlink():
            continue  # An untracked nested repository; git cannot diff a directory.
        patch += subprocess.run(
            # Files over 1 MiB show as binary so stray data cannot bloat every patch.
            ["git", "-c", "core.bigFileThreshold=1m", "diff", "--no-index"]
            + ["--", "/dev/null", relative],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ).stdout
    return patch
