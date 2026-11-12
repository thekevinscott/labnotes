import json
import tomllib
from typing import Any
from pathlib import Path

import pytest

from labnotes.cli import main


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def labnotes(
    project: Path, argv: list[str], capsys: pytest.CaptureFixture[str]
) -> list[dict[str, Any]]:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(project / ".labnotes.toml"), *argv, "--format", "json"])
    assert exit_info.value.code == 0
    rows: list[dict[str, Any]] = json.loads(capsys.readouterr().out)
    return rows


@pytest.fixture
def project(tmp_path: Path) -> Path:
    write(
        tmp_path / ".labnotes.toml",
        '[experiments]\npath = "notes/{experiment}"\n'
        '[files]\npath = "notes/{experiment}/*.md"\n'
        '[runs]\npath = "data/{experiment}/{run}"\n',
    )
    write(tmp_path / "notes/alpha/plan.md", "plan")
    write(
        tmp_path / "notes/alpha/experiment.toml",
        'name = "Alpha study"\n[params]\nm = ["a", "b"]\n',
    )
    write(tmp_path / "notes/beta/readme.md", "readme")
    write(
        tmp_path / "data/alpha/brave-fox/run.json",
        json.dumps(
            {
                "params": {"m": "a"},
                "created": "2026-10-17T00:00:00Z",
                "ended": "2026-10-17T00:01:00Z",
                "exit_code": 0,
            }
        ),
    )
    write(
        tmp_path / "data/gamma/lone-run/run.json",
        json.dumps({"created": "2026-10-16T00:00:00Z"}),
    )
    return tmp_path


def test_lists_an_experiments_runs(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    [run] = labnotes(project, ["experiments", "alpha", "runs"], capsys)

    assert run["id"] == "brave-fox"
    assert run["folder"] == "data/alpha/brave-fox"
    assert json.loads(run["params"]) == {"m": "a"}


@pytest.mark.parametrize("contents", ["{not json", ""])
def test_lists_a_damaged_run_record(
    project: Path, capsys: pytest.CaptureFixture[str], contents: str
) -> None:
    write(project / "data/alpha/broken/run.json", contents)

    rows = labnotes(project, ["experiments", "alpha", "runs"], capsys)

    assert {row["id"] for row in rows} == {"brave-fox", "broken"}
    [broken] = [row for row in rows if row["id"] == "broken"]
    assert broken["folder"] == "data/alpha/broken"
    assert "run.json" in broken["error"]


def test_creates_a_new_experiment(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(project / ".labnotes.toml"), "experiments", "new", "delta"])
    assert exit_info.value.code == 0

    text = (project / "notes/delta/experiment.toml").read_text(encoding="utf-8")
    assert tomllib.loads(text)["repeats"] == 1
