import json
import os
import sys
import time
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


def browse_processes(root: Path) -> list[psutil.Process]:
    config = str(root / ".labnotes.toml")
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (cmdline := process.info["cmdline"] or [])
        and "experiments" in cmdline
        and "daemon" not in cmdline
    ]


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


def browse(
    terminal, root: Path, argv: str = "", env: dict[str, str] | None = None
) -> Terminal:
    command = Path(sys.executable).parent / "labnotes"
    return terminal(
        f"{command} -c {root / '.labnotes.toml'} experiments {argv}",
        rows=30,
        cols=160,
        env=env or {},
    )


def shows_the_list(term: Terminal) -> None:
    expect(term.get_by_text("Alpha study")).to_be_visible()
    expect(term.get_by_text("beta")).to_be_visible()


def shows_alpha(term: Terminal) -> None:
    expect(term.get_by_text("Alpha study")).to_be_visible()
    expect(term.get_by_text("20261017-000000/second")).to_be_visible()
    expect(term.get_by_text("source-language")).to_be_visible()


def open_list(terminal, root: Path, env: dict[str, str] | None = None) -> Terminal:
    term = browse(terminal, root, "", env)
    shows_the_list(term)
    return term


def open_alpha(terminal, root: Path, env: dict[str, str] | None = None) -> Terminal:
    term = browse(terminal, root, "alpha", env)
    shows_alpha(term)
    return term


def open_alpha_from_list(
    terminal, root: Path, env: dict[str, str] | None = None
) -> Terminal:
    term = open_list(terminal, root, env)
    term.key_enter()
    shows_alpha(term)
    return term


SCREENS = pytest.mark.parametrize(
    "open_screen",
    [open_list, open_alpha, open_alpha_from_list],
    ids=["experiments screen", "experiment screen", "list then experiment"],
)


def close(term: Terminal) -> None:
    term.key_ctrl_c()
    term.wait()


@SCREENS
def test_screen_adds_no_inotify_watches(terminal, root: Path, open_screen) -> None:
    term = open_screen(terminal, root)

    (process,) = browse_processes(root)
    assert inotify_watches(process.pid) == 0

    close(term)


@SCREENS
def test_screen_reads_nothing_from_the_project(
    terminal, tmp_path: Path, root: Path, audited: dict[str, str], open_screen
) -> None:
    term = open_screen(terminal, root, audited)
    # Long enough for a periodic refresh to happen.
    time.sleep(6)

    close(term)
    reads = tmp_path / "reads.log"
    assert not reads.exists(), sorted(set(reads.read_text().splitlines()))


@SCREENS
def test_screen_starts_a_daemon_on_demand(terminal, root: Path, open_screen) -> None:
    assert daemons(root) == []
    term = open_screen(terminal, root)

    assert daemons(root) != []

    close(term)


def test_runs_written_before_the_daemon_started_show(terminal, root: Path) -> None:
    term = open_alpha(terminal, root)
    expect(term.get_by_text("20261017-000000/first")).to_be_visible()
    close(term)


def test_a_run_written_by_hand_while_open_is_not_picked_up(
    terminal, root: Path
) -> None:
    term = open_alpha(terminal, root)

    write(
        root / "alpha/runs/20261018-000000/manual/run.json",
        json.dumps({"created": "2026-10-18T00:00:00Z", "exit_code": 0}),
    )
    time.sleep(3)
    assert not term.get_by_text(
        "20261018-000000/manual"
    ).is_visible(), term.to_snapshot()

    close(term)


def test_notes_written_outside_labnotes_while_open_are_not_picked_up(
    terminal, root: Path
) -> None:
    term = open_list(terminal, root)

    write(root / "gamma/files/notes.md", "notes")
    time.sleep(3)
    assert not term.get_by_text("gamma").is_visible(), term.to_snapshot()

    close(term)


def test_a_second_window_gets_the_daemons_snapshot(terminal, root: Path) -> None:
    first = open_alpha(terminal, root)
    write(
        root / "alpha/runs/20261018-000000/manual/run.json",
        json.dumps({"created": "2026-10-18T00:00:00Z", "exit_code": 0}),
    )

    second = open_alpha(terminal, root)
    time.sleep(3)
    assert not second.get_by_text(
        "20261018-000000/manual"
    ).is_visible(), second.to_snapshot()

    close(second)
    close(first)
