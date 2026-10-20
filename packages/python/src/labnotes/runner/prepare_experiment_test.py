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
            "labnotes.runner.prepare_experiment.runs_parent",
            return_value=tmp_path / "runs" / "exp",
        ) as runs_parent,
        mock.patch(
            "labnotes.runner.prepare_experiment.read_experiment_config"
        ) as read_experiment_config,
        mock.patch(
            "labnotes.runner.prepare_experiment.file_text",
            new=mock.AsyncMock(return_value="source"),
        ) as file_text,
    ):
        yield {
            "runs_parent": runs_parent,
            "read_experiment_config": read_experiment_config,
            "file_text": file_text,
        }


def make_config(root: Path) -> mock.Mock:
    return mock.Mock(
        root=root,
        experiments="notes/{experiment}",
        runs="data/{experiment}/{run}",
        mode="fill",
        concurrency=3,
    )


def prepare(
    root: Path, experiment_config: Path | None = None, concurrency: int | None = 2
) -> tuple[object, int, Path]:
    return asyncio.run(
        prepare_experiment(make_config(root), "exp", experiment_config, concurrency)
    )


def test_reads_the_experiment_and_makes_its_runs_folder(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    path = tmp_path / "notes" / "exp" / "experiment.toml"

    experiment, concurrency, runs = prepare(tmp_path)

    collaborators["file_text"].assert_awaited_once_with(tmp_path, path)
    collaborators["read_experiment_config"].assert_called_once_with(
        path, "source", "fill", 3
    )
    collaborators["runs_parent"].assert_called_once_with(
        tmp_path, "data/{experiment}/{run}", "exp"
    )
    assert experiment is collaborators["read_experiment_config"].return_value
    assert concurrency == 2
    assert runs == tmp_path / "runs" / "exp"
    assert runs.is_dir()


def test_reads_the_named_experiment_config(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    path = tmp_path / "other.toml"

    prepare(tmp_path, path)

    collaborators["read_experiment_config"].assert_called_once_with(
        path, "source", "fill", 3
    )


def test_needs_an_experiment_config(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["file_text"].return_value = None

    with pytest.raises(ValueError, match="No experiment.toml for exp at "):
        prepare(tmp_path)

    assert not (tmp_path / "runs").exists()


def test_falls_back_to_the_experiment_concurrency(
    tmp_path: Path, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["read_experiment_config"].return_value.concurrency = 4

    assert prepare(tmp_path, concurrency=None)[1] == 4
