import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.daemon.control_run import control_run


@pytest.fixture
def client() -> Iterator[mock.AsyncMock]:
    client = mock.AsyncMock()
    with (
        mock.patch(
            "labnotes.daemon.control_run.daemon_running",
            new=mock.AsyncMock(return_value=True),
        ),
        mock.patch("labnotes.daemon.control_run.daemon_client") as daemon_client,
    ):
        daemon_client.return_value.__aenter__.return_value = client
        yield client
    daemon_client.assert_called_once_with(Path("/p"))


def test_sends_the_control_to_the_daemon(client: mock.AsyncMock) -> None:
    client.post.return_value = mock.Mock(is_success=True)

    assert asyncio.run(control_run(Path("/p"), "exp", "kill", ["exp/r1"])) is None

    client.post.assert_awaited_once_with(
        "/experiments/exp/kill", json={"args": ["exp/r1"]}
    )


def test_says_why_the_daemon_refused(client: mock.AsyncMock) -> None:
    client.post.return_value = mock.Mock(is_success=False)
    client.post.return_value.json.return_value = {"error": "No kill for nope."}

    said = asyncio.run(control_run(Path("/p"), "nope", "kill", []))

    assert said == "No kill for nope."


def test_says_when_nothing_runs() -> None:
    with (
        mock.patch(
            "labnotes.daemon.control_run.daemon_running",
            new=mock.AsyncMock(return_value=False),
        ) as daemon_running,
        mock.patch("labnotes.daemon.control_run.daemon_client") as daemon_client,
    ):
        said = asyncio.run(control_run(Path("/p"), "exp", "finish", []))

    assert said == "Nothing is running."
    daemon_running.assert_awaited_once_with(Path("/p"))
    daemon_client.assert_not_called()
