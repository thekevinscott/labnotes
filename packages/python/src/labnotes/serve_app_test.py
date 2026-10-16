from pathlib import Path
from unittest import mock

from labnotes.serve_app import serve_app


def test_builds_the_app_from_the_env_vars() -> None:
    env = {
        "LABNOTES_EXPERIMENTS_FOLDER": "/exp",
        "LABNOTES_DATA_FOLDER": "/data",
        "LABNOTES_KERNEL_IDLE_MINUTES": "45",
    }
    with (
        mock.patch.dict("os.environ", env),
        mock.patch("labnotes.serve_app.create_app") as create_app,
    ):
        assert serve_app() is create_app.return_value
    create_app.assert_called_once_with(Path("/exp"), Path("/data"), 45)
