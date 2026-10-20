import hashlib
import os
from pathlib import Path


# Unix socket paths cap at 107 bytes, so the socket can't live in a deep project.
# A fixed folder, not XDG_RUNTIME_DIR or TMPDIR, so every shell finds the daemon.
def socket_path(root: Path) -> Path:
    folder = Path("/tmp") / f"labnotes-{os.getuid()}"
    folder.mkdir(mode=0o700, exist_ok=True)
    digest = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:16]
    return folder / f"{digest}.sock"
