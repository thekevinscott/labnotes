import json
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import write

from labnotes.cli import main

SCRIPT = """
import sys
from pathlib import Path

args = sys.argv[1:]
out = Path(args.pop(args.index("--out") + 1))
args.remove("--out")
(out / "out.txt").write_text(" ".join(args))
"""


def labnotes(project: Path, argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(project / ".labnotes.toml"), *argv])
    return exit_info.value.code


def listed(
    project: Path, capsys: pytest.CaptureFixture[str], *names: str
) -> list[dict[str, Any]]:
    capsys.readouterr()
    assert labnotes(project, ["experiments", *names, "--format", "json"]) == 0
    rows: list[dict[str, Any]] = json.loads(capsys.readouterr().out)
    return rows


def outputs(runs: Path) -> list[str]:
    return sorted(path.read_text() for path in runs.glob("**/out.txt"))


def test_one_experiment_runs_from_the_labnotes_toml_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "study"
    write(root / "script.py", SCRIPT)
    write(
        root / ".labnotes.toml",
        "[experiment]\n"
        f'name = "Study"\ncommand = "{sys.executable} script.py --out {{run_dir}}"\n'
        '[experiment.params]\nm = ["a"]\n',
    )

    [row] = listed(root, capsys)
    assert (row["name"], row["display_name"]) == ("study", "Study")

    assert labnotes(root, ["experiments", "study", "run"]) == 0
    assert outputs(root / "runs") == ["--m a"]


def test_experiment_toml_layers_over_the_labnotes_toml(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "study"
    write(root / "script.py", SCRIPT)
    write(
        root / ".labnotes.toml",
        f'[experiment]\ncommand = "{sys.executable} script.py --out {{run_dir}}"\n'
        '[experiment.params]\nm = ["a"]\nn = ["x"]\n',
    )
    write(root / "experiment.toml", 'name = "Layered"\n[params]\nn = ["y", "z"]\n')

    [row] = listed(root, capsys)
    assert row["display_name"] == "Layered"

    assert labnotes(root, ["experiments", "study", "run"]) == 0
    assert outputs(root / "runs") == ["--m a --n y", "--m a --n z"]


def test_many_experiments_share_the_defaults(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path / "script.py", SCRIPT)
    write(
        tmp_path / ".labnotes.toml",
        '[experiments]\npath = "{experiment}"\n'
        f'[experiment]\ncommand = "{sys.executable} script.py --out {{run_dir}}"\n',
    )
    write(tmp_path / "alpha/experiment.toml", '[params]\nm = ["a"]\n')
    write(tmp_path / "beta/files/notes.md", "notes")

    command = f"{sys.executable} script.py --out {{run_dir}}"
    [alpha] = listed(tmp_path, capsys, "alpha")
    [beta] = listed(tmp_path, capsys, "beta")
    assert json.loads(alpha["config"]) == {"command": command, "params": {"m": ["a"]}}
    assert json.loads(beta["config"]) == {"command": command}

    assert labnotes(tmp_path, ["experiments", "alpha", "run"]) == 0
    assert outputs(tmp_path / "alpha/runs") == ["--m a"]
