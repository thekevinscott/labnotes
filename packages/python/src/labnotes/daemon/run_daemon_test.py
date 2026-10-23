import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.daemon.run_daemon import run_daemon


@pytest.fixture
def collaborators(tmp_path: Path) -> Iterator[dict[str, mock.MagicMock]]:
    sock = tmp_path / ".labnotes.sock"
    with (
        mock.patch(
            "labnotes.daemon.run_daemon.socket_path", return_value=sock
        ) as socket_path,
        mock.patch("labnotes.daemon.run_daemon.daemon_app") as daemon_app,
        mock.patch("labnotes.daemon.run_daemon.DaemonServer") as server,
        mock.patch("labnotes.daemon.run_daemon.signal") as signal,
        mock.patch("labnotes.daemon.run_daemon.uvicorn.Config") as uvicorn_config,
        mock.patch(
            "labnotes.daemon.run_daemon.exit_when_idle", new=mock.AsyncMock()
        ) as exit_when_idle,
        mock.patch(
            "labnotes.daemon.run_daemon.finalize_lost_runs", new=mock.AsyncMock()
        ) as finalize_lost_runs,
    ):
        server.return_value.serve = mock.AsyncMock(
            side_effect=lambda: sock.write_text("")
        )
        yield {
            "sock": sock,  # type: ignore[dict-item]
            "socket_path": socket_path,
            "daemon_app": daemon_app,
            "server": server,
            "signal": signal,
            "uvicorn_config": uvicorn_config,
            "exit_when_idle": exit_when_idle,
            "finalize_lost_runs": finalize_lost_runs,
        }


def serve(config: object, handlers: dict[object, object]) -> None:
    async def go() -> None:
        loop = asyncio.get_running_loop()
        with mock.patch.object(
            loop, "add_signal_handler", side_effect=handlers.__setitem__
        ):
            await run_daemon(config)  # type: ignore[arg-type]

    asyncio.run(go())


def test_serves_the_app_on_the_projects_socket(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    config = mock.Mock(root=Path("/p"))
    app = collaborators["daemon_app"].return_value
    handlers: dict[object, object] = {}

    serve(config, handlers)

    collaborators["socket_path"].assert_called_once_with(Path("/p"))
    collaborators["daemon_app"].assert_called_once_with(config)
    collaborators["uvicorn_config"].assert_called_once_with(
        app, uds=str(collaborators["sock"]), lifespan="off", log_level="warning"
    )
    collaborators["server"].assert_called_once_with(
        collaborators["uvicorn_config"].return_value
    )
    signal = collaborators["signal"]
    assert handlers == {signal.SIGTERM: app.state.stop, signal.SIGHUP: app.state.stop}
    collaborators["exit_when_idle"].assert_called_once_with(
        collaborators["server"].return_value, app.state.idle
    )
    assert not collaborators["sock"].exists()  # type: ignore[attr-defined]


def test_removes_the_socket_when_serving_fails(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    sock: Path = collaborators["sock"]  # type: ignore[assignment]
    sock.write_text("")
    collaborators["server"].return_value.serve.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        serve(mock.Mock(root=Path("/p")), {})

    assert not sock.exists()


def test_reports_a_failure_to_serve_before_the_socket_exists(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["server"].return_value.serve.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        serve(mock.Mock(root=Path("/p")), {})


def test_finalizes_lost_runs_before_serving(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    config = mock.Mock(root=Path("/p"))
    collaborators["server"].return_value.serve.side_effect = lambda: (
        collaborators["finalize_lost_runs"].assert_awaited_once_with(config)
    )

    serve(config, {})

    collaborators["finalize_lost_runs"].assert_awaited_once_with(config)
