import json
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

    term.write("q")
    term.wait()


@pytest.mark.parametrize("argv", ["alpha", "alpha runs"])
def test_opens_straight_on_a_named_experiment(
    terminal, tmp_path: Path, argv: str
) -> None:
    term = labnotes(terminal, project(tmp_path), argv)
    expect(term.get_by_text("2✓ 0✕")).to_be_visible()

    term.write("q")
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

    term.write("q")
    term.wait()


def test_lists_an_experiment_that_appears_while_open(terminal, tmp_path: Path) -> None:
    root = project(tmp_path)
    term = labnotes(terminal, root, "")
    expect(term.get_by_text("beta")).to_be_visible()

    write(root / "gamma/files/notes.md", "notes")
    expect(term.get_by_text("gamma")).to_be_visible()

    term.write("q")
    term.wait()


def test_prints_and_exits_when_format_is_given(terminal, tmp_path: Path) -> None:
    term = labnotes(terminal, project(tmp_path), "--format json")
    expect(term.get_by_text('"display_name": "alpha"')).to_be_visible()
    term.wait()

    assert term.exit_code == 0
