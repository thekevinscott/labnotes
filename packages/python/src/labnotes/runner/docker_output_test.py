from unittest import mock

from labnotes.runner.docker_output import docker_output


def test_returns_docker_stdout() -> None:
    with mock.patch(
        "labnotes.runner.docker_output.subprocess.run",
        return_value=mock.Mock(returncode=0, stdout="container-id\n"),
    ) as run:
        assert docker_output("ps", "--quiet") == "container-id\n"
    run.assert_called_once_with(
        ["docker", "ps", "--quiet"],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )


def test_unreachable_docker_returns_none() -> None:
    with mock.patch(
        "labnotes.runner.docker_output.subprocess.run",
        side_effect=OSError("daemon unavailable"),
    ):
        assert docker_output("ps") is None
