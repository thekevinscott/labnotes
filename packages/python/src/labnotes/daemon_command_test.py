from unittest import mock

import pytest

from labnotes.daemon_command import daemon


def test_hidden_daemon_command_serves_named_experiment() -> None:
    with (
        mock.patch("labnotes.daemon_command.load_config") as load,
        mock.patch(
            "labnotes.daemon_command.serve_daemon", new=mock.AsyncMock()
        ) as serve,
    ):
        with pytest.raises(SystemExit) as result:
            daemon.main(["exp"])
    assert result.value.code == 0
    serve.assert_awaited_once_with(load.return_value, "exp")


def test_hidden_daemon_needs_config(capsys: pytest.CaptureFixture[str]) -> None:
    with mock.patch("labnotes.daemon_command.load_config", return_value=None):
        with pytest.raises(SystemExit) as result:
            daemon.main(["exp"])
    assert result.value.code == 1
    assert "No .labnotes.toml here" in capsys.readouterr().err
