import json
import time
import sys
from pathlib import Path

import pytest
from curtaincall import Terminal, expect


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def project(root: Path) -> Path:
    write(root / ".labnotes.toml", "")
    write(root / "alpha/experiment.toml", 'command = "go"\nmode = "adhoc"\n')
    for run in ("20261017-000000/first", "20261017-000000/second"):
        write(
            root / f"alpha/runs/{run}/run.json",
            json.dumps({"created": "2026-10-17T00:00:00Z", "exit_code": 0}),
        )
    write(root / "beta/files/notes.md", "notes")
    return root


def labnotes(terminal, root: Path, argv: str) -> Terminal:
    command = Path(sys.executable).parent / "labnotes"
    return terminal(
        f"{command} -c {root / '.labnotes.toml'} experiments {argv}",
        rows=30,
        cols=120,
    )


def test_browses_from_the_list_into_an_experiment_and_back(
    terminal, tmp_path: Path
) -> None:
    term = labnotes(terminal, project(tmp_path), "")
    expect(term.get_by_text("display_name")).to_be_visible()
    expect(term.get_by_text("beta")).to_be_visible()

    term.key_enter()
    expect(term.get_by_text("20261017-000000")).to_be_visible()
    expect(term.get_by_text("2✓ 0✕")).to_be_visible()

    term.key_enter()
    expect(term.get_by_text("second")).to_be_visible()

    term.key_escape()
    expect(term.get_by_text("display_name")).to_be_visible()

    term.key_ctrl_c()
    term.wait()


@pytest.mark.parametrize("argv", ["alpha", "alpha runs"])
def test_opens_straight_on_a_named_experiment(
    terminal, tmp_path: Path, argv: str
) -> None:
    term = labnotes(terminal, project(tmp_path), argv)
    expect(term.get_by_text("2✓ 0✕")).to_be_visible()

    term.key_ctrl_c()
    term.wait()


def test_shows_a_run_that_lands_while_the_experiment_is_open(
    terminal, tmp_path: Path
) -> None:
    root = project(tmp_path)
    term = labnotes(terminal, root, "alpha")
    expect(term.get_by_text("2✓ 0✕")).to_be_visible()

    write(
        root / "alpha/runs/20261018-000000/first/run.json",
        json.dumps({"created": "2026-10-18T00:00:00Z", "exit_code": 1}),
    )
    expect(term.get_by_text("20261018-000000")).to_be_visible()
    expect(term.get_by_text("0✓ 1✕")).to_be_visible()

    term.key_ctrl_c()
    term.wait()


def test_lists_an_experiment_that_appears_while_open(terminal, tmp_path: Path) -> None:
    root = project(tmp_path)
    term = labnotes(terminal, root, "")
    expect(term.get_by_text("beta")).to_be_visible()

    write(root / "gamma/files/notes.md", "notes")
    expect(term.get_by_text("gamma")).to_be_visible()

    term.key_ctrl_c()
    term.wait()


def test_opens_a_run_and_follows_its_output(terminal, tmp_path: Path) -> None:
    root = project(tmp_path)
    run = root / "alpha/runs/20261017-000000/second"
    write(run / "stdout.log", "hello from second\n")
    write(run / "stderr.log", "warned on stderr\n")
    term = labnotes(terminal, root, "alpha")
    expect(term.get_by_text("2✓ 0✕")).to_be_visible()

    term.key_enter()
    expect(term.get_by_text("second")).to_be_visible()
    term.key_down()
    term.key_enter()
    expect(term.get_by_text("20261017-000000/second")).to_be_visible()
    expect(term.get_by_text("hello from second")).to_be_visible()
    expect(term.get_by_text("warned on stderr")).to_be_visible()

    with (run / "stdout.log").open("a", encoding="utf-8") as log:
        log.write("appended later\n")
    expect(term.get_by_text("appended later")).to_be_visible()

    term.key_escape()
    expect(term.get_by_text("first")).to_be_visible()
    expect(term.get_by_text("hello from second")).not_to_be_visible()

    term.key_enter()
    expect(term.get_by_text("appended later")).to_be_visible()

    term.key_ctrl_c()
    term.wait()


def test_prints_and_exits_when_format_is_given(terminal, tmp_path: Path) -> None:
    term = labnotes(terminal, project(tmp_path), "--format json")
    expect(term.get_by_text('"display_name": "alpha"')).to_be_visible()
    term.wait()

    assert term.exit_code == 0


LAST_LINE = """\
from pathlib import Path

from labnotes import view


def last_line(folder):
    lines = (Path(folder) / "stderr.log").read_text().splitlines()
    return lines[-1] if lines else ""


@view.serve
def runs(columns):
    return [*columns, {"key": "last", "label": "last stderr"}], lambda row: {
        **row,
        "last": last_line(row["folder"]),
    }
"""


def viewed(root: Path, script: str) -> Path:
    write(root / "alpha/view.py", script)
    write(
        root / "alpha/experiment.toml",
        'command = "go"\nmode = "adhoc"\n'
        f"[views]\nruns = {json.dumps(f'{sys.executable} alpha/view.py')}\n",
    )
    for run in ("first", "second"):
        write(root / f"alpha/runs/20261017-000000/{run}/stderr.log", f"{run} warmup\n")
    return root


def test_adds_columns_from_a_runs_view_and_follows_run_files(
    terminal, tmp_path: Path
) -> None:
    root = viewed(project(tmp_path), LAST_LINE)
    term = labnotes(terminal, root, "alpha")
    expect(term.get_by_text("last stderr")).to_be_visible()

    term.key_enter()
    expect(term.get_by_text("second warmup")).to_be_visible()

    stderr = root / "alpha/runs/20261017-000000/second/stderr.log"
    with stderr.open("a", encoding="utf-8") as log:
        log.write("step 2 of 9\n")
    expect(term.get_by_text("step 2 of 9")).to_be_visible()
    expect(term.get_by_text("second warmup")).not_to_be_visible()

    term.key_ctrl_c()
    term.wait()


def test_keeps_redrawing_while_a_run_writes_continuously(
    terminal, tmp_path: Path
) -> None:
    root = viewed(project(tmp_path), LAST_LINE)
    term = labnotes(terminal, root, "alpha")
    expect(term.get_by_text("last stderr")).to_be_visible()
    term.key_enter()
    expect(term.get_by_text("second warmup")).to_be_visible()

    stderr = root / "alpha/runs/20261017-000000/second/stderr.log"
    with stderr.open("a", encoding="utf-8") as log:
        for step in range(200):
            log.write(f"step {step}\n")
            log.flush()
            time.sleep(0.01)
    expect(term.get_by_text("step 199")).to_be_visible()

    term.key_ctrl_c()
    term.wait()


def test_reports_a_bad_answer_and_a_slow_one(terminal, tmp_path: Path) -> None:
    script = (
        "import time\nfrom labnotes import view\n\n\n@view.serve\n"
        "def runs(columns):\n    time.sleep(0.2)\n"
        '    return columns, lambda row: {**row, "extra": 1}\n'
    )
    term = labnotes(terminal, viewed(project(tmp_path), script), "alpha")
    expect(term.get_by_text("unknown columns extra")).to_be_visible()
    expect(term.get_by_text("runs view took")).to_be_visible()
    expect(term.get_by_text("2✓ 0✕")).to_be_visible()

    term.key_ctrl_c()
    term.wait()
