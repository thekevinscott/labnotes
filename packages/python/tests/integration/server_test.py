from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import write
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
    app = create_app(read_config(tmp_path / ".labnotes.toml"))
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


NOTE = "/experiments/alpha/notes/plan.md"
PLAN = "```python\na = 1\n```\n\n```python\na + 1\n```\n"


def test_saves_a_note_to_disk(client: TestClient, tmp_path: Path) -> None:
    response = client.put(NOTE, json={"base": PLAN, "content": "# New ✓\n"})

    assert response.status_code == 204
    assert (tmp_path / "alpha/files/plan.md").read_text(encoding="utf-8") == "# New ✓\n"


def test_serves_a_saved_note_straight_after_the_save(client: TestClient) -> None:
    client.put(NOTE, json={"base": PLAN, "content": "# New ✓\n"})

    assert client.get(NOTE).text == "# New ✓\n"


def test_refuses_a_save_based_on_a_stale_note(
    client: TestClient, tmp_path: Path
) -> None:
    write(tmp_path / "alpha/files/plan.md", "edited elsewhere")

    response = client.put(NOTE, json={"base": PLAN, "content": "mine"})

    assert response.status_code == 409
    assert response.json() == {"content": "edited elsewhere"}
    assert (tmp_path / "alpha/files/plan.md").read_text() == "edited elsewhere"


def test_runs_the_blocks_of_a_saved_note(client: TestClient) -> None:
    client.put(NOTE, json={"base": PLAN, "content": "```python\n40 + 2\n```\n"})

    assert ">42<" in client.post(RUN, json={"block": 0}).text


def test_save_requires_json(client: TestClient) -> None:
    response = client.put(NOTE, content="x", headers={"content-type": "text/plain"})

    assert response.status_code == 415


def test_save_rejects_an_unknown_note(client: TestClient) -> None:
    response = client.put(
        NOTE.replace("plan", "nope"), json={"base": "", "content": "x"}
    )

    assert response.status_code == 404
