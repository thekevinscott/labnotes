import json
import sys
from pathlib import Path
from typing import Any

import pytest

from labnotes.cli import main

SCRIPT = "import sys\nprint(*sys.argv[1:])\n"


def make_project(root: Path, mode: str = "matrix") -> Path:
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(SCRIPT)
    (root / "exp" / "experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\n'
        f'repeats = 2\nmode = "{mode}"\n[params]\nm = ["a", "b"]\nn = [1, 2]\n'
    )
    return root


def labnotes(project: Path, argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(project / ".labnotes.toml"), "experiments", "exp", *argv])
    return exit_info.value.code


def params(project: Path) -> list[dict[str, Any]]:
    return sorted(
        (
            json.loads(path.read_text(encoding="utf-8"))["params"]
            for path in (project / "exp" / "runs").glob("**/run.json")
        ),
        key=json.dumps,
    )


def test_runs_only_the_cells_matching_every_param(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = make_project(tmp_path)

    assert labnotes(project, ["run", "--m=a", "--n=2"]) == 0

    assert params(project) == [{"m": "a", "n": 2}] * 2
    assert capsys.readouterr().out.endswith("2 passed, 0 failed.\n")


def test_keeps_the_full_matrix_as_the_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = make_project(tmp_path)

    assert labnotes(project, ["run", "--m=a"]) == 0
    assert labnotes(project, ["run"]) == 0

    assert params(project) == sorted(
        [{"m": m, "n": n} for m in "ab" for n in (1, 2)] * 2, key=json.dumps
    )
    assert capsys.readouterr().out.endswith("4 passed, 0 failed.\n")


def test_filters_adhoc_runs_the_same_way(tmp_path: Path) -> None:
    project = make_project(tmp_path, "adhoc")

    assert labnotes(project, ["run", "--n=1"]) == 0

    assert params(project) == sorted(
        [{"m": "a", "n": 1}, {"m": "b", "n": 1}] * 2, key=json.dumps
    )


@pytest.mark.parametrize(
    ("flag", "error"),
    [
        ("--size=a", "No param size. Params: m, n."),
        ("--m=c", "No value c for m. Values: a, b."),
    ],
)
def test_refuses_a_param_or_value_the_experiment_does_not_declare(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], flag: str, error: str
) -> None:
    project = make_project(tmp_path)

    assert labnotes(project, ["run", flag]) == 1

    assert f"Error: {error}" in capsys.readouterr().err
    assert not (project / "exp" / "runs").exists()


def test_refuses_two_values_for_one_param(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = make_project(tmp_path)

    assert labnotes(project, ["run", "--m=a", "--m=b"]) == 2

    assert "--m given twice. Pass one value per param." in capsys.readouterr().err
