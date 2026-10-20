from unittest import mock

from labnotes.daemon.daemon_server import DaemonServer


def test_leaves_signals_to_the_daemon() -> None:
    server = DaemonServer(mock.Mock())
    with mock.patch("signal.signal") as signal:
        with server.capture_signals():
            pass

    signal.assert_not_called()
