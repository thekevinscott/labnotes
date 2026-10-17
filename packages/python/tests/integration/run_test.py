import json
import sys
from pathlib import Path
from typing import Any

import pytest

from labnotes.cli import main

SCRIPT = """
import sys
from pathlib import Path

args = sys.argv[1:]
Path("out.txt").write_text(" ".join(args))
print("ran", *args)
sys.exit(1 if "b" in args else 0)
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "script.py", SCRIPT)
    write(
        tmp_path / "exp" / "experiment.toml",
        f'command = "{sys.executable} {tmp_path}/script.py"\n'
        'repeats = 2\n[params]\nm = ["a", "b"]\n',
    )
    return tmp_path


def labnotes(project: Path, argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(project / ".labnotes.toml"), *argv])
    return exit_info.value.code


def runs(project: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8")) | {"folder": path.parent}
        for path in sorted((project / "exp" / "runs").glob("*/run.json"))
    ]


def test_runs_every_param_combination_repeats_times(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert labnotes(project, ["experiments", "exp", "run", "--concurrency", "2"]) == 1

    recorded = runs(project)
    assert sorted(run["params"]["m"] for run in recorded) == ["a", "a", "b", "b"]
    for run in recorded:
        m = run["params"]["m"]
        assert run["exit_code"] == (1 if m == "b" else 0)
        assert run["created"] <= run["ended"]
        assert (run["folder"] / "out.txt").read_text() == f"--m {m}"
        assert (run["folder"] / "stdout.log").read_text() == f"ran --m {m}\n"
    assert capsys.readouterr().out.endswith("2 passed, 2 failed.\n")


def test_reruns_only_the_runs_that_failed(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    labnotes(project, ["experiments", "exp", "run"])
    labnotes(project, ["experiments", "exp", "run"])

    recorded = runs(project)
    assert sorted(run["params"]["m"] for run in recorded) == ["a", "a"] + ["b"] * 4
