import json
import subprocess
import sys
from pathlib import Path

import pytest
from curtaincall import expect

LABNOTES = Path(sys.executable).parent / "labnotes"
ACTIONS = "runs, run, attach or stop"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def project(root: Path) -> Path:
    write(root / ".labnotes.toml", "")
    write(root / "alpha/experiment.toml", 'continues = false\ncommand = "go"\n')
    write(
        root / "alpha/runs/20261017-000000/first/run.json",
        json.dumps({"created": "2026-10-17T00:00:00Z", "exit_code": 0}),
    )
    return root


def in_terminal(terminal, root: Path, argv: str):
    term = terminal(
        f"{LABNOTES} -c {root / '.labnotes.toml'} experiments {argv}",
        rows=30,
        cols=300,
    )
    expect(term).to_have_exited(timeout=30)
    return term


@pytest.mark.parametrize("argv", ["", "alpha"])
def test_a_bare_command_names_the_actions_in_a_terminal(
    terminal, tmp_path: Path, argv: str
) -> None:
    term = in_terminal(terminal, project(tmp_path), argv)

    assert term.get_by_text(ACTIONS).is_visible(), term.to_snapshot()
    assert term.exit_code == 2, term.to_snapshot()


@pytest.mark.parametrize("argv", [[], ["alpha"]])
def test_a_bare_command_names_the_actions_when_piped(
    tmp_path: Path, argv: list[str]
) -> None:
    root = project(tmp_path)
    result = subprocess.run(
        [str(LABNOTES), "-c", str(root / ".labnotes.toml"), "experiments", *argv],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 2, result.stdout + result.stderr
    assert ACTIONS in result.stderr
    assert result.stdout == ""


def test_runs_prints_the_table_and_exits_in_a_terminal(
    terminal, tmp_path: Path
) -> None:
    term = in_terminal(terminal, project(tmp_path), "alpha runs")

    assert term.get_by_text("20261017-000000/first").is_visible(), term.to_snapshot()
    assert term.exit_code == 0, term.to_snapshot()
