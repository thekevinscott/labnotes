import json
import os
from pathlib import Path

import psutil
import pytest
from curtaincall import Terminal, expect

from conftest import Tui

# Directories elsewhere in the repo: not on any screen, so not worth a watch.
ELSEWHERE = 40
# alpha/runs, its invocation folder, and the two run folders under it.
ALPHA_RUN_DIRS = 4


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_json(language: str) -> str:
    return json.dumps(
        {
            "created": "2026-10-17T00:00:00Z",
            "exit_code": 0,
            "params": {"source-language": language},
        }
    )


def project(root: Path) -> Path:
    write(root / ".labnotes.toml", "")
    write(
        root / "alpha/experiment.toml",
        'name = "Alpha study"\ncontinues = false\ncommand = "go"\n'
        '[params]\nsource-language = ["en", "fr"]\n',
    )
    write(root / "alpha/files/plan.md", "# The plan\n")
    for run, language in (("first", "en"), ("second", "fr")):
        write(root / f"alpha/runs/20261017-000000/{run}/run.json", run_json(language))
    write(root / "beta/files/notes.md", "notes")
    for index in range(ELSEWHERE):
        (root / f"data/set-{index:02}").mkdir(parents=True)
    return root


def browse_processes(root: Path) -> list[psutil.Process]:
    config = str((root / ".labnotes.toml").resolve())
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if "experiments" in (cmdline := process.info["cmdline"] or [])
        and "daemon" not in cmdline
        and any(str(Path(arg).resolve()) == config for arg in cmdline if "/" in arg)
    ]


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
def test_uvx_labnotes_screen_watches_only_what_it_shows(
    tmp_path: Path, tui: Tui, argv: tuple[str, ...], enter: bool
) -> None:
    root = project(tmp_path / "project")

    term = tui(root, "experiments", *argv, cols=160)
    if argv:
        shows_alpha(term)
    else:
        shows_the_list(term)
    if enter:
        term.key_enter()
        shows_alpha(term)

    browse = browse_processes(root)
    assert browse
    assert sum(inotify_watches(process.pid) for process in browse) <= ALPHA_RUN_DIRS

    tui.quit(term)


def test_uvx_labnotes_experiment_screen_shows_a_new_run_live(
    tmp_path: Path, tui: Tui
) -> None:
    root = project(tmp_path / "project")

    term = tui(root, "experiments", "alpha", cols=160)
    shows_alpha(term)
    write(root / "alpha/runs/20261018-000000/first/run.json", run_json("en"))
    expect(term.get_by_text("20261018-000000/first")).to_be_visible()

    tui.quit(term)
