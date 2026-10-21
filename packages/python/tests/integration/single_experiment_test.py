import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import write
from starlette.testclient import TestClient

from labnotes.cli import main
from labnotes.create_app import create_app
from labnotes.read_config import read_config


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "surprisals"
    write(root / ".labnotes.toml", '[files]\npath = "notes/"\n')
    write(root / "experiment.toml", 'name = "Surprisals"\ncommand = "go"\n')
    write(root / "notes/plan.md", "# The plan\n")
    write(root / "data/inner/experiment.toml", 'name = "Not an experiment"\n')
    write(
        root / "runs/brave-fox/run.json",
        json.dumps({"params": {"m": "a"}, "created": "2026-10-17T00:00:00Z"}),
    )
    return root


def labnotes(
    project: Path, argv: list[str], capsys: pytest.CaptureFixture[str]
) -> list[dict[str, Any]]:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(project / ".labnotes.toml"), *argv, "--format", "json"])
    assert exit_info.value.code == 0
    rows: list[dict[str, Any]] = json.loads(capsys.readouterr().out)
    return rows


def test_lists_the_folder_as_the_one_experiment(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = labnotes(project, ["experiments"], capsys)

    assert [(r["name"], r["display_name"], r["files"], r["runs"]) for r in rows] == [
        ("surprisals", "Surprisals", 1, 1)
    ]


def test_lists_its_runs(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    [run] = labnotes(project, ["experiments", "surprisals", "runs"], capsys)

    assert (run["id"], run["folder"]) == ("brave-fox", "runs/brave-fox")


def test_refuses_a_new_experiment(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(project / ".labnotes.toml"), "experiments", "new", "delta"])

    assert exit_info.value.code == 1
    assert "can't hold others" in capsys.readouterr().err


@pytest.fixture
def client(project: Path) -> Iterator[TestClient]:
    with TestClient(create_app(read_config(project / ".labnotes.toml"))) as client:
        yield client


def test_the_web_app_shows_its_notes_and_runs(client: TestClient) -> None:
    page = client.get("/experiments/surprisals")

    assert "brave-fox" in page.text
    assert "plan.md" in client.get("/experiments/surprisals?tab=notebooks").text
    note = client.get("/experiments/surprisals/notes/plan.md")
    assert "The plan" in note.text
