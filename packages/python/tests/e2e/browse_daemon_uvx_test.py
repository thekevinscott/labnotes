import json
import os
import time
from pathlib import Path

import psutil
import pytest
from curtaincall import Terminal, expect

from conftest import Tui


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


def labnotes_processes(root: Path) -> tuple[list[psutil.Process], list[psutil.Process]]:
    """Split this project's labnotes processes into browse ones and daemons."""
    config = str((root / ".labnotes.toml").resolve())
    browse, daemons = [], []
    for process in psutil.process_iter(["cmdline"]):
        cmdline = process.info["cmdline"] or []
        if not any(str(Path(arg).resolve()) == config for arg in cmdline if "/" in arg):
            continue
        (daemons if "daemon" in cmdline else browse).append(process)
    return browse, daemons


def inotify_watches(pid: int) -> int:
    watches = 0
    try:
        fds = os.listdir(f"/proc/{pid}/fd")
    except FileNotFoundError:
        return 0
    for fd in fds:
        try:
            if os.readlink(f"/proc/{pid}/fd/{fd}") != "anon_inode:inotify":
                continue
            info = Path(f"/proc/{pid}/fdinfo/{fd}").read_text()
        except FileNotFoundError:
            continue
        watches += sum(line.startswith("inotify wd:") for line in info.splitlines())
    return watches


def shows_the_list(term: Terminal) -> None:
    expect(term.get_by_text("Alpha study")).to_be_visible(timeout=60)
    expect(term.get_by_text("beta")).to_be_visible()


def shows_alpha(term: Terminal) -> None:
    expect(term.get_by_text("Alpha study")).to_be_visible(timeout=60)
    expect(term.get_by_text("20261017-000000/second")).to_be_visible()
    expect(term.get_by_text("source-language")).to_be_visible()


@pytest.mark.parametrize(
    "argv,enter",
    [((), False), (("alpha",), False), ((), True)],
    ids=["experiments screen", "experiment screen", "list then experiment"],
)
def test_uvx_labnotes_screen_reads_only_from_the_daemon(
    tmp_path: Path, tui: Tui, argv: tuple[str, ...], enter: bool
) -> None:
    root = project(tmp_path / "project")
    hooks = tmp_path / "audit"
    write(hooks / "sitecustomize.py", AUDIT)
    reads = tmp_path / "reads.log"
    env = {
        "PYTHONPATH": str(hooks),
        "BROWSE_AUDIT_ROOT": str(root.resolve()),
        "BROWSE_AUDIT_LOG": str(reads),
    }

    term = tui(root, "experiments", *argv, env=env, cols=160)
    if argv:
        shows_alpha(term)
    else:
        shows_the_list(term)
    if enter:
        term.key_enter()
        shows_alpha(term)

    browse, daemons = labnotes_processes(root)
    assert browse
    assert sum(inotify_watches(process.pid) for process in browse) == 0
    assert daemons, "browsing did not start a daemon"
    time.sleep(6)
    assert not reads.exists(), sorted(set(reads.read_text().splitlines()))

    tui.quit(term)


def test_uvx_labnotes_reads_hand_written_runs_once(tmp_path: Path, tui: Tui) -> None:
    root = project(tmp_path / "project")

    first = tui(root, "experiments", "alpha", cols=160)
    shows_alpha(first)
    expect(first.get_by_text("20261017-000000/first")).to_be_visible()

    write(
        root / "alpha/runs/20261018-000000/manual/run.json",
        json.dumps({"created": "2026-10-18T00:00:00Z", "exit_code": 0}),
    )
    second = tui(root, "experiments", "alpha", cols=160)
    shows_alpha(second)
    time.sleep(3)
    for term in (first, second):
        assert not term.get_by_text(
            "20261018-000000/manual"
        ).is_visible(), term.to_snapshot()

    tui.quit(second)
    tui.quit(first)


def test_uvx_labnotes_does_not_refresh_notes_edited_outside(
    tmp_path: Path, tui: Tui
) -> None:
    root = project(tmp_path / "project")

    term = tui(root, "experiments", cols=160)
    shows_the_list(term)
    write(root / "gamma/files/notes.md", "notes")
    time.sleep(3)
    assert not term.get_by_text("gamma").is_visible(), term.to_snapshot()

    tui.quit(term)
