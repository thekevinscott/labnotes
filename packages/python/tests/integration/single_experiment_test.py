import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import write
from starlette.testclient import TestClient

from labnotes.cli import main
from labnotes.default_counts import DEFAULT_COUNTS
from labnotes.read_config import read_config
from labnotes.tables.list_experiment_runs import list_experiment_runs
from labnotes.tables.open_tables import open_tables
from labnotes.create_app import create_app


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "surprisals"
    write(root / ".labnotes.toml", '[files]\npath = "notes/"\n')
    write(
        root / "experiment.toml",
        'name = "Surprisals"\ncontinues = false\ncommand = "go"\n',
    )
    write(root / "notes/plan.md", "# The plan\n")
    write(root / "data/inner/experiment.toml", 'name = "Not an experiment"\n')
    write(
        root / "runs/brave-fox/run.json",
        json.dumps({"params": {"m": "a"}, "created": "2026-10-17T00:00:00Z"}),
    )
    return root


def stored_runs(root: Path, name: str) -> list[dict[str, Any]]:
    async def read() -> list[dict[str, Any]]:
        tables = open_tables(read_config(root / ".labnotes.toml"))
        return await list_experiment_runs(tables, name, DEFAULT_COUNTS)

    return asyncio.run(read())


def test_reads_its_runs(project: Path) -> None:
    [run] = stored_runs(project, "surprisals")

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
