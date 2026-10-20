from pathlib import Path
from unittest import mock

from labnotes.serve_app import serve_app


def test_builds_the_app_from_the_env_vars() -> None:
    with (
        mock.patch.dict("os.environ", {"LABNOTES_CONFIG": "/p/.labnotes.toml"}),
        mock.patch("labnotes.serve_app.read_config") as read_config,
        mock.patch("labnotes.serve_app.create_app") as create_app,
    ):
        assert serve_app() is create_app.return_value
    read_config.assert_called_once_with(Path("/p/.labnotes.toml"))
    create_app.assert_called_once_with(read_config.return_value)
