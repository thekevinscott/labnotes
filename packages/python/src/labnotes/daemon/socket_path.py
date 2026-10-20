from pathlib import Path

SOCKET_NAME = ".labnotes.sock"


def socket_path(root: Path) -> Path:
    return root / SOCKET_NAME
