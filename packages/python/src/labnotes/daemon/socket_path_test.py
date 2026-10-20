from pathlib import Path

from labnotes.daemon.socket_path import socket_path


def test_sits_in_the_project_root() -> None:
    assert socket_path(Path("/p")) == Path("/p/.labnotes.sock")
