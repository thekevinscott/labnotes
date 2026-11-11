import json
import os
import sys
from pathlib import Path

import psutil
import pytest
from curtaincall import Terminal, expect

# Directories elsewhere in the repo: not on any screen, so not worth a watch.
ELSEWHERE = 40
# alpha/runs, its invocation folder, and the two run folders under it.
ALPHA_RUN_DIRS = 4


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_json(language: str, exit_code: int = 0) -> str:
    return json.dumps(
        {
            "created": "2026-10-17T00:00:00Z",
            "ended": "2026-10-17T00:00:01Z",
            "exit_code": exit_code,
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
def root(tmp_path: Path) -> Path:
    return project(tmp_path / "project")


def browse(terminal, root: Path, argv: str = "") -> Terminal:
    command = Path(sys.executable).parent / "labnotes"
    return terminal(
        f"{command} -c {root / '.labnotes.toml'} experiments {argv}",
        rows=30,
        cols=160,
    )


def shows_the_list(term: Terminal) -> None:
    expect(term.get_by_text("Alpha study")).to_be_visible()
    expect(term.get_by_text("beta")).to_be_visible()


def shows_alpha(term: Terminal) -> None:
    expect(term.get_by_text("Alpha study")).to_be_visible()
    expect(term.get_by_text("20261017-000000/second")).to_be_visible()
    expect(term.get_by_text("source-language")).to_be_visible()


def open_list(terminal, root: Path) -> Terminal:
    term = browse(terminal, root)
    shows_the_list(term)
    return term


def open_alpha(terminal, root: Path) -> Terminal:
    term = browse(terminal, root, "alpha")
    shows_alpha(term)
    return term


def open_alpha_from_list(terminal, root: Path) -> Terminal:
    term = open_list(terminal, root)
    term.key_enter()
    shows_alpha(term)
    return term


def close(term: Terminal) -> None:
    term.key_ctrl_c()
    term.wait()


@pytest.mark.parametrize(
    "open_screen",
    [open_list, open_alpha, open_alpha_from_list],
    ids=["experiments screen", "experiment screen", "list then experiment"],
)
def test_screen_watches_only_what_it_shows(terminal, root: Path, open_screen) -> None:
    term = open_screen(terminal, root)

    (process,) = browse_processes(root)
    assert inotify_watches(process.pid) <= ALPHA_RUN_DIRS

    close(term)


def test_experiment_screen_shows_a_new_run_live(terminal, root: Path) -> None:
    term = open_alpha(terminal, root)

    write(root / "alpha/runs/20261018-000000/first/run.json", run_json("en"))
    expect(term.get_by_text("20261018-000000/first")).to_be_visible()

    close(term)


def test_experiment_screen_shows_a_status_change_live(terminal, root: Path) -> None:
    term = open_alpha(terminal, root)
    expect(term.get_by_text("✕")).not_to_be_visible()

    write(
        root / "alpha/runs/20261017-000000/second/run.json",
        run_json("fr", exit_code=1),
    )
    expect(term.get_by_text("✕")).to_be_visible()

    close(term)
