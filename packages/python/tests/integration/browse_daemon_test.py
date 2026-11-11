import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import psutil
import pytest
from curtaincall import Terminal, expect

# Logs every Python-level file open or directory listing the browse TUI makes
# under the project. The daemon it starts is allowed to read the project.
AUDIT = """\
import os
import sys

ROOT = os.environ["BROWSE_AUDIT_ROOT"]
LOG = os.environ["BROWSE_AUDIT_LOG"]
CONFIG = os.path.join(ROOT, ".labnotes.toml")


def audit(event, args):
    if event not in ("open", "os.scandir", "os.listdir"):
        return
    if "experiments" not in sys.argv or "daemon" in sys.argv:
        return
    path = args[0] if args else None
    if path is None or isinstance(path, int):
        return
    path = os.path.realpath(os.fsdecode(path))
    if path.startswith(ROOT + os.sep) and path != CONFIG:
        with open(LOG, "a", encoding="utf-8") as log:
            log.write(event + " " + path + "\\n")


sys.addaudithook(audit)
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def project(root: Path) -> Path:
    write(root / ".labnotes.toml", "")
    write(
        root / "alpha/experiment.toml",
        'name = "Alpha study"\ncontinues = false\ncommand = "go"\n'
        '[params]\nsource-language = ["en", "fr"]\n',
    )
    write(root / "alpha/files/plan.md", "# The plan\n")
    for run, language in (("first", "en"), ("second", "fr")):
        write(
            root / f"alpha/runs/20261017-000000/{run}/run.json",
            json.dumps(
                {
                    "created": "2026-10-17T00:00:00Z",
                    "exit_code": 0,
                    "params": {"source-language": language},
                }
            ),
        )
    write(root / "beta/files/notes.md", "notes")
    return root


def daemons(root: Path) -> list[psutil.Process]:
    config = str((root / ".labnotes.toml").resolve())
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if "daemon" in (cmdline := process.info["cmdline"] or [])
        and any(str(Path(arg).resolve()) == config for arg in cmdline if "/" in arg)
    ]


def browse_process(root: Path) -> psutil.Process:
    config = str(root / ".labnotes.toml")
    (found,) = [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (cmdline := process.info["cmdline"] or [])
        and "experiments" in cmdline
        and "daemon" not in cmdline
    ]
    return found


def inotify_watches(pid: int) -> int:
    watches = 0
    for fd in os.listdir(f"/proc/{pid}/fd"):
        try:
            if os.readlink(f"/proc/{pid}/fd/{fd}") != "anon_inode:inotify":
                continue
            info = Path(f"/proc/{pid}/fdinfo/{fd}").read_text()
        except FileNotFoundError:
            continue
        watches += sum(line.startswith("inotify wd:") for line in info.splitlines())
    return watches


@pytest.fixture
def root(tmp_path: Path) -> Iterator[Path]:
    yield project(tmp_path / "project")
    owners = daemons(tmp_path / "project")
    for process in owners:
        process.terminate()
    _, alive = psutil.wait_procs(owners, timeout=15)
    for process in alive:
        process.kill()


@pytest.fixture
def audited(tmp_path: Path, root: Path) -> dict[str, str]:
    hooks = tmp_path / "audit"
    write(hooks / "sitecustomize.py", AUDIT)
    return {
        "PYTHONPATH": str(hooks),
        "BROWSE_AUDIT_ROOT": str(root.resolve()),
        "BROWSE_AUDIT_LOG": str(tmp_path / "reads.log"),
    }


def browse(terminal, root: Path, env: dict[str, str] | None = None) -> Terminal:
    command = Path(sys.executable).parent / "labnotes"
    return terminal(
        f"{command} -c {root / '.labnotes.toml'} experiments",
        rows=30,
        cols=160,
        env=env or {},
    )


def shows_everything(term: Terminal) -> None:
    expect(term.get_by_text("Alpha study")).to_be_visible()
    expect(term.get_by_text("beta")).to_be_visible()
    term.key_enter()
    expect(term.get_by_text("20261017-000000/second")).to_be_visible()
    expect(term.get_by_text("source-language")).to_be_visible()
    expect(term.get_by_text("fr")).to_be_visible()


def test_browsing_adds_no_inotify_watches(terminal, root: Path) -> None:
    term = browse(terminal, root)
    shows_everything(term)

    assert inotify_watches(browse_process(root).pid) == 0

    term.key_ctrl_c()
    term.wait()


def test_browsing_reads_nothing_from_the_project(
    terminal, tmp_path: Path, root: Path, audited: dict[str, str]
) -> None:
    term = browse(terminal, root, audited)
    shows_everything(term)
    term.key_escape()
    expect(term.get_by_text("Alpha study")).to_be_visible()

    term.key_ctrl_c()
    term.wait()
    reads = tmp_path / "reads.log"
    assert not reads.exists(), sorted(set(reads.read_text().splitlines()))


def test_browsing_starts_a_daemon_on_demand(terminal, root: Path) -> None:
    assert daemons(root) == []
    term = browse(terminal, root)
    shows_everything(term)

    assert daemons(root) != []

    term.key_ctrl_c()
    term.wait()
