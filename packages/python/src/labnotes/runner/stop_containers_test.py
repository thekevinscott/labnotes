from pathlib import Path
from unittest import mock

from labnotes.runner.stop_containers import stop_containers


def test_kills_only_containers_with_the_run_label(tmp_path: Path) -> None:
    run = str(tmp_path / "run")
    with (
        mock.patch(
            "labnotes.runner.stop_containers.shutil.which", return_value="docker"
        ),
        mock.patch(
            "labnotes.runner.stop_containers.docker_output",
            side_effect=["first\nsecond\n", "first\n", "second\n"],
        ) as docker,
    ):
        stop_containers(run)

    assert docker.call_args_list == [
        mock.call(
            "ps", "--quiet", "--no-trunc", "--filter", f"label=labnotes.run={run}"
        ),
        mock.call("kill", "first"),
        mock.call("kill", "second"),
    ]


def test_does_nothing_without_docker(tmp_path: Path) -> None:
    with (
        mock.patch("labnotes.runner.stop_containers.shutil.which", return_value=None),
        mock.patch("labnotes.runner.stop_containers.docker_output") as docker,
    ):
        stop_containers(str(tmp_path))
    docker.assert_not_called()
