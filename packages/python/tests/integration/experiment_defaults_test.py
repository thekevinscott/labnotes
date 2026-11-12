import sys
from pathlib import Path

import pytest
from conftest import write

from labnotes.cli import main
from conftest import run_tui_command

SCRIPT = """
import sys
from pathlib import Path

args = sys.argv[1:]
out = Path(args.pop(args.index("--out") + 1))
args.remove("--out")
(out / "out.txt").write_text(" ".join(args))
"""


def labnotes(project: Path, argv: list[str]) -> int | str | None:
    if len(argv) >= 3 and argv[0] == "experiments" and argv[2] == "run":
        return run_tui_command(project, argv)
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(project / ".labnotes.toml"), *argv])
    return exit_info.value.code


def outputs(runs: Path) -> list[str]:
    return sorted(path.read_text() for path in runs.glob("**/out.txt"))


def test_one_experiment_runs_from_the_labnotes_toml_alone(
    tmp_path: Path,
) -> None:
    root = tmp_path / "study"
    write(root / "script.py", SCRIPT)
    write(
        root / ".labnotes.toml",
        "[experiment]\n"
        f'name = "Study"\ncontinues = false\ncommand = "{sys.executable} script.py --out {{run_dir}}"\n'
        '[experiment.params]\nm = ["a"]\n',
    )

    assert labnotes(root, ["experiments", "study", "run"]) == 0
    assert outputs(root / "runs") == ["--m a"]


def test_experiment_toml_layers_over_the_labnotes_toml(
    tmp_path: Path,
) -> None:
    root = tmp_path / "study"
    write(root / "script.py", SCRIPT)
    write(
        root / ".labnotes.toml",
        f'[experiment]\ncontinues = false\ncommand = "{sys.executable} script.py --out {{run_dir}}"\n'
        '[experiment.params]\nm = ["a"]\nn = ["x"]\n',
    )
    write(root / "experiment.toml", 'name = "Layered"\n[params]\nn = ["y", "z"]\n')

    assert labnotes(root, ["experiments", "study", "run"]) == 0
    assert outputs(root / "runs") == ["--m a --n y", "--m a --n z"]


def test_many_experiments_share_the_defaults(
    tmp_path: Path,
) -> None:
    write(tmp_path / "script.py", SCRIPT)
    write(
        tmp_path / ".labnotes.toml",
        '[experiments]\npath = "{experiment}"\n'
        f'[experiment]\ncontinues = false\ncommand = "{sys.executable} script.py --out {{run_dir}}"\n',
    )
    write(tmp_path / "alpha/experiment.toml", '[params]\nm = ["a"]\n')
    write(tmp_path / "beta/files/notes.md", "notes")

    assert labnotes(tmp_path, ["experiments", "alpha", "run"]) == 0
    assert outputs(tmp_path / "alpha/runs") == ["--m a"]
    assert labnotes(tmp_path, ["experiments", "beta", "run"]) == 0
    assert outputs(tmp_path / "beta/runs") == [""]
