import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.prepare_experiment import prepare_experiment


@pytest.fixture
def collaborators(tmp_path: Path) -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.runner.prepare_experiment.read_experiment_config"
        ) as read_experiment_config,
        mock.patch(
            "labnotes.runner.prepare_experiment.file_text",
            new=mock.AsyncMock(return_value="source"),
        ) as file_text,
        mock.patch("labnotes.runner.prepare_experiment.check_subset") as check_subset,
        mock.patch("labnotes.runner.prepare_experiment.check_args") as check_args,
    ):
        yield {
            "read_experiment_config": read_experiment_config,
            "file_text": file_text,
            "check_subset": check_subset,
            "check_args": check_args,
        }


def make_config(root: Path) -> mock.Mock:
    return mock.Mock(
        experiment=None,
        defaults={},
        path=root / ".labnotes.toml",
        root=root,
        experiments="notes/{experiment}",
        runs="data/{experiment}/{run}",
        mode="matrix",
        concurrency=3,
        retries=4,
    )


def prepare(
    root: Path, experiment_config: Path | None = None, concurrency: int | None = 2
) -> tuple[object, int]:
    return asyncio.run(
        prepare_experiment(make_config(root), "exp", experiment_config, concurrency)
    )


def test_reads_the_experiment(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    path = tmp_path / "notes" / "exp" / "experiment.toml"

    experiment, concurrency = prepare(tmp_path)

    collaborators["file_text"].assert_awaited_once_with(tmp_path, path)
    collaborators["read_experiment_config"].assert_called_once_with(
        path, "source", "matrix", 3, 4, {}
    )
    assert experiment is collaborators["read_experiment_config"].return_value
    assert concurrency == 2
    collaborators["check_subset"].assert_not_called()
    collaborators["check_args"].assert_not_called()


def test_checks_the_subset_against_the_params(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    experiment = collaborators["read_experiment_config"].return_value
    collaborators["check_subset"].side_effect = ValueError("No param size.")

    with pytest.raises(ValueError, match=r"^No param size\.$"):
        asyncio.run(
            prepare_experiment(make_config(tmp_path), "exp", None, 2, {"size": "s"})
        )

    collaborators["check_subset"].assert_called_once_with(
        experiment.params, {"size": "s"}
    )


def test_checks_the_args_against_the_params_and_command(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    experiment = collaborators["read_experiment_config"].return_value
    collaborators["check_args"].side_effect = ValueError("--m is a param.")

    with pytest.raises(ValueError, match=r"^--m is a param\.$"):
        asyncio.run(
            prepare_experiment(make_config(tmp_path), "exp", None, 2, None, ["--m"])
        )

    collaborators["check_args"].assert_called_once_with(
        experiment.params, experiment.command, ["--m"]
    )


def test_reads_the_named_experiment_config(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    path = tmp_path / "other.toml"

    prepare(tmp_path, path)

    collaborators["read_experiment_config"].assert_called_once_with(
        path, "source", "matrix", 3, 4, {}
    )


def test_needs_an_experiment_config(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["file_text"].return_value = None

    with pytest.raises(ValueError, match="No experiment.toml for exp at "):
        prepare(tmp_path)


def test_falls_back_to_the_experiment_concurrency(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["read_experiment_config"].return_value.concurrency = 4

    assert prepare(tmp_path, concurrency=None)[1] == 4


def test_reads_the_root_experiment_toml_for_the_one_experiment(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    config = mock.Mock(
        experiment="exp", root=tmp_path, experiments="", mode="adhoc", concurrency=1
    )

    asyncio.run(prepare_experiment(config, "exp", None, None))

    collaborators["file_text"].assert_awaited_once_with(
        tmp_path, tmp_path / "experiment.toml"
    )


def test_refuses_another_name_for_the_one_experiment(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    config = mock.Mock(experiment="exp", root=tmp_path, experiments="")

    with pytest.raises(ValueError, match="No experiment other; this project is"):
        asyncio.run(prepare_experiment(config, "other", None, None))


def test_runs_from_the_defaults_alone(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["file_text"].return_value = None
    config = make_config(tmp_path)
    config.defaults = {"command": "go"}

    asyncio.run(prepare_experiment(config, "exp", None, None))

    collaborators["read_experiment_config"].assert_called_once_with(
        tmp_path / ".labnotes.toml", "", "matrix", 3, 4, {"command": "go"}
    )
