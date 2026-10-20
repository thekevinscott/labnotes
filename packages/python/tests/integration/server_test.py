from collections.abc import Iterator
from pathlib import Path

import pytest
from served import write
from starlette.testclient import TestClient

from labnotes.create_app import create_app
from labnotes.read_config import read_config

RUN = "/experiments/alpha/notes/plan.md/run"
RESTART = "/experiments/alpha/notes/plan.md/restart"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    write(tmp_path / ".labnotes.toml", "")
    write(
        tmp_path / "alpha/files/plan.md",
        "```python\na = 1\n```\n\n```python\na + 1\n```\n",
    )
    write(tmp_path / "alpha/files/other.md", "```python\nb = 1\n```\n")
    app = create_app(read_config(tmp_path / ".labnotes.toml"), 30)
    with TestClient(app) as client:
        yield client


def test_runs_blocks_in_one_kernel_per_note(client: TestClient) -> None:
    client.post(RUN, json={"block": 0})

    response = client.post(RUN, json={"block": 1})

    assert response.status_code == 200
    assert ">2<" in response.text


def test_restart_only_touches_its_own_note(client: TestClient) -> None:
    client.post(RUN, json={"block": 0})

    response = client.post("/experiments/alpha/notes/other.md/restart", json={})

    assert response.status_code == 204
    assert ">2<" in client.post(RUN, json={"block": 1}).text


def test_restart_before_any_run_succeeds(client: TestClient) -> None:
    assert client.post(RESTART, json={}).status_code == 204


@pytest.mark.parametrize("body", [{"block": 2}, {"block": -1}, {"block": "0"}, {}])
def test_run_rejects_a_missing_block(client: TestClient, body: object) -> None:
    assert client.post(RUN, json=body).status_code == 400


@pytest.mark.parametrize("path", [RUN, RESTART])
def test_rejects_an_unknown_note(client: TestClient, path: str) -> None:
    unknown = path.replace("plan.md", "nope.md")

    assert client.post(unknown, json={"block": 0}).status_code == 404


@pytest.mark.parametrize("path", [RUN, RESTART])
def test_requires_json_so_forms_on_other_sites_cannot_post(
    client: TestClient, path: str
) -> None:
    response = client.post(
        path, content="block=0", headers={"content-type": "text/plain"}
    )

    assert response.status_code == 415


def test_unknown_experiment_is_not_found(client: TestClient) -> None:
    assert client.get("/experiments/nope").status_code == 404
