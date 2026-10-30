import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import daemon, write

from labnotes.cli import main

RECORD = """
import json
import socket
import sys

server = socket.socket(socket.AF_UNIX)
server.bind(sys.argv[1])
server.listen()
while True:
    client, _ = server.accept()
    with open(sys.argv[2], "a") as log:
        log.write(json.dumps(client.recv(65536).decode()) + "\\n")
    client.close()
"""


def make_project(root: Path, env: str) -> Path:
    write(
        root / ".labnotes.toml",
        '[experiments]\npath = "{experiment}"\n'
        f"[experiment.env]\nCOLOR = {json.dumps(env)}\n",
    )
    write(
        root / "exp" / "experiment.toml",
        f'command = \'{sys.executable} -c "import os; print(os.environ[\\"COLOR\\"])"\'\n',
    )
    return root


def run(project: Path) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(project / ".labnotes.toml"), "experiments", "exp", "run"])
    return exit_info.value.code


def printed(project: Path) -> set[str]:
    records = (project / "exp" / "runs").rglob("run.json")
    return {(record.parent / "stdout.log").read_text().strip() for record in records}


def legacy_socket(root: Path) -> Path:
    # Where labnotes 0.0.136 and older listen: one socket per project, any version.
    digest = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:16]
    return Path("/tmp") / f"labnotes-{os.getuid()}" / f"{digest}.sock"


@pytest.fixture
def old_daemon(tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    project = make_project(tmp_path, "new")
    path = legacy_socket(project)
    path.parent.mkdir(exist_ok=True)
    log = tmp_path / "old-daemon.log"
    log.touch()
    server = subprocess.Popen([sys.executable, "-c", RECORD, str(path), str(log)])
    try:
        while not path.exists():
            time.sleep(0.05)
        yield project, log
    finally:
        server.kill()
        server.wait()
        path.unlink()


def test_each_run_reads_the_project_config_as_it_is_now(tmp_path: Path) -> None:
    project = make_project(tmp_path, "first")
    for _ in daemon(project):
        assert run(project) == 0
        assert printed(project) == {"first"}
        make_project(project, "second")
        assert run(project) == 0

    assert printed(project) == {"first", "second"}


def test_a_new_version_leaves_an_older_daemon_alone(
    old_daemon: tuple[Path, Path],
) -> None:
    project, log = old_daemon

    assert run(project) == 0

    assert printed(project) == {"new"}
    assert log.read_text() == ""
