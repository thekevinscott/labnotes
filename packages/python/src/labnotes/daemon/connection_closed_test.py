import asyncio
from unittest import mock

import pytest

from labnotes.daemon.connection_closed import connection_closed


@pytest.mark.parametrize(
    "replies",
    [[b"stray", b""], [b"", b"never read"], [ConnectionResetError()]],
)
def test_returns_once_the_peer_closes_or_the_connection_fails(
    replies: list[object],
) -> None:
    client = mock.Mock()
    loop = mock.Mock(sock_recv=mock.AsyncMock(side_effect=replies))
    with mock.patch(
        "labnotes.daemon.connection_closed.asyncio.get_running_loop",
        return_value=loop,
    ):
        asyncio.run(connection_closed(client))
    client.setblocking.assert_called_once_with(False)
    expected = 2 if replies[0] == b"stray" else 1
    assert loop.sock_recv.await_args_list == [mock.call(client, 1024)] * expected
