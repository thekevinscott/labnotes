import json
import os
import subprocess
from pathlib import Path

import pytest

from conftest import Tui

ACTIONS = "runs, run, attach or stop"


def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    run = root / "alpha/runs/20261017-000000/first"
    run.mkdir(parents=True)
    (run / "run.json").write_text(
        json.dumps({"created": "2026-10-17T00:00:00Z", "exit_code": 0})
    )
    (root / "alpha/experiment.toml").write_text('continues = false\ncommand = "go"\n')
    (root / ".labnotes.toml").write_text("")
    return root


@pytest.mark.parametrize("argv", [(), ("alpha",)])
def test_uvx_bare_command_names_the_actions_in_a_terminal(
    tmp_path: Path, tui: Tui, argv: tuple[str, ...]
) -> None:
    term = tui(project(tmp_path), "experiments", *argv, cols=300)

    assert tui.exited(term) == 2, term.to_snapshot()
    assert term.get_by_text(ACTIONS).is_visible(), term.to_snapshot()


@pytest.mark.parametrize("argv", [[], ["alpha"]])
def test_uvx_bare_command_names_the_actions_when_piped(
    tmp_path: Path, uvx: dict[str, str], argv: list[str]
) -> None:
    result = subprocess.run(
        ["uvx", "labnotes", "experiments", *argv],
        cwd=project(tmp_path),
        env={**os.environ, **uvx},
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 2, result.stdout + result.stderr
    assert ACTIONS in result.stderr


def test_uvx_runs_prints_the_table_and_exits_in_a_terminal(
    tmp_path: Path, tui: Tui
) -> None:
    term = tui(project(tmp_path), "experiments", "alpha", "runs", cols=300)

    assert tui.exited(term) == 0, term.to_snapshot()
    assert term.get_by_text("20261017-000000/first").is_visible(), term.to_snapshot()
