from pathlib import Path
from unittest import mock

from labnotes.daemon.daemon_client import daemon_client


def test_talks_to_the_projects_socket() -> None:
    with (
        mock.patch("labnotes.daemon.daemon_client.httpx2") as httpx2,
        mock.patch(
            "labnotes.daemon.daemon_client.socket_path", return_value=Path("/p/s")
        ) as socket_path,
    ):
        client = daemon_client(Path("/p"))

    socket_path.assert_called_once_with(Path("/p"))
    httpx2.AsyncHTTPTransport.assert_called_once_with(uds="/p/s")
    httpx2.AsyncClient.assert_called_once_with(
        transport=httpx2.AsyncHTTPTransport.return_value,
        base_url="http://labnotes",
        timeout=None,
    )
    assert client is httpx2.AsyncClient.return_value
