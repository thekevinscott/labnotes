import hashlib
import os
import tempfile
from pathlib import Path


# Unix socket paths cap at 107 bytes, so the socket can't live in a deep project.
def socket_path(root: Path) -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    folder = (
        Path(runtime) / "labnotes"
        if runtime
        else Path(tempfile.gettempdir()) / f"labnotes-{os.getuid()}"
    )
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    digest = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:16]
    return folder / f"{digest}.sock"
