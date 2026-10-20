import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from labnotes.create_app import create_app
from labnotes.read_config import read_config


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(project: Path, name: str, params: dict[str, object], **fields: object) -> None:
    record = {"params": params, "created": f"2026-10-17T00:00:0{name[-1]}Z", **fields}
    write(project / f"alpha/runs/{name}/run.json", json.dumps(record))


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    write(tmp_path / ".labnotes.toml", "")
    write(
        tmp_path / "alpha/experiment.toml",
        'name = "Alpha study"\ncommand = "go"\nrepeats = 2\nmode = "fill"\n'
        '[params]\nsource-language = ["en", "fr"]\n',
    )
    write(tmp_path / "alpha/files/plan.md", "# The plan\n\n```python\n1 + 1\n```\n")
    run(tmp_path, "run1", {"source-language": "en"}, exit_code=0)
    run(tmp_path, "run2", {"source-language": "en"}, exit_code=0)
    run(tmp_path, "run3", {"source-language": "fr"}, exit_code=1)
    run(tmp_path, "run4", {"source-language": "fr"}, exit_code=0, excluded=True)
    write(tmp_path / "beta/files/notes.md", "beta notes")
    app = create_app(read_config(tmp_path / ".labnotes.toml"), 30)
    with TestClient(app) as client:
        yield client


def test_lists_experiments_with_their_progress(client: TestClient) -> None:
    text = client.get("/").text

    assert ">Alpha study</a>" in text
    assert ">beta</a>" in text
    assert "2 experiments" in text
    assert "4 runs recorded" in text
    assert '<span class="num">2<span class="of">/4</span></span>' in text


def test_restart_rejects_an_unknown_note(client: TestClient) -> None:
    response = client.post("/experiments/alpha/notes/nope.md/restart", json={})

    assert response.status_code == 404


def test_shows_a_broken_counts_rule_instead_of_failing(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(
        tmp_path / "alpha/experiment.toml",
        'command = "go"\ncounts = "nope ="\n[params]\nm = ["a"]\n',
    )
    run(tmp_path, "run1", {"m": "a"}, exit_code=0)
    app = create_app(read_config(tmp_path / ".labnotes.toml"), 30)

    with TestClient(app) as client:
        index = client.get("/")

    assert index.status_code == 200
    assert "counts rule doesn't work" in index.text
