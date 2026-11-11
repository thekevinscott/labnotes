import json
import os
from pathlib import Path

import psutil
from curtaincall import expect

from conftest import Tui


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


def test_uvx_labnotes_browses_through_the_daemon_without_watching_files(
    tmp_path: Path, tui: Tui
) -> None:
    root = project(tmp_path / "project")

    term = tui(root, "experiments", cols=160)
    expect(term.get_by_text("Alpha study")).to_be_visible(timeout=60)
    expect(term.get_by_text("beta")).to_be_visible()
    term.key_enter()
    expect(term.get_by_text("20261017-000000/second")).to_be_visible()
    expect(term.get_by_text("source-language")).to_be_visible()

    browse, daemons = labnotes_processes(root)
    assert browse
    assert sum(inotify_watches(process.pid) for process in browse) == 0
    assert daemons, "browsing did not start a daemon"

    term.key_escape()
    expect(term.get_by_text("Alpha study")).to_be_visible()
    tui.quit(term)
