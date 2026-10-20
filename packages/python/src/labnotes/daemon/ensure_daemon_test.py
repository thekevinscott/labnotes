import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.daemon.ensure_daemon import START_SECONDS, ensure_daemon

CONFIG = mock.Mock(root=Path("/p"), path=Path("/p/.labnotes.toml"))


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.daemon.ensure_daemon.daemon_running", new=mock.AsyncMock()
        ) as daemon_running,
        mock.patch("labnotes.daemon.ensure_daemon.subprocess") as subprocess,
        mock.patch(
            "labnotes.daemon.ensure_daemon.asyncio.sleep", new=mock.AsyncMock()
        ) as sleep,
        mock.patch("labnotes.daemon.ensure_daemon.sys.executable", "/py"),
    ):
        yield {
            "daemon_running": daemon_running,
            "subprocess": subprocess,
            "sleep": sleep,
        }


def test_uses_a_running_daemon(collaborators: dict[str, mock.MagicMock]) -> None:
    collaborators["daemon_running"].return_value = True

    asyncio.run(ensure_daemon(CONFIG))

    collaborators["daemon_running"].assert_awaited_once_with(Path("/p"))
    collaborators["subprocess"].Popen.assert_not_called()


def test_starts_a_daemon_and_waits_for_it(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["daemon_running"].side_effect = [False, False, True]

    asyncio.run(ensure_daemon(CONFIG))

    subprocess = collaborators["subprocess"]
    subprocess.Popen.assert_called_once_with(
        ["/py", "-m", "labnotes", "-c", "/p/.labnotes.toml", "daemon"],
        cwd=Path("/p"),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    assert collaborators["sleep"].await_count == 2
    collaborators["sleep"].assert_awaited_with(0.1)


def test_gives_up_on_a_daemon_that_never_listens(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["daemon_running"].return_value = False

    with pytest.raises(ValueError, match="did not start in 10s"):
        asyncio.run(ensure_daemon(CONFIG))

    assert START_SECONDS == 10
    assert collaborators["sleep"].await_count == 100
