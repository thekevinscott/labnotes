import asyncio
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.start_experiment import start_experiment


def test_prepares_and_runs_in_this_process_after_finalizing_lost_runs() -> None:
    config = mock.Mock(root=Path("/tmp/project"), runs="{experiment}/runs/{run}")
    experiment = mock.sentinel.experiment
    report = mock.Mock()
    listen = mock.Mock()
    results = [{"exit_code": 0}]
    snapshot = mock.sentinel.snapshot
    with (
        mock.patch(
            "labnotes.runner.start_experiment.prepare_experiment",
            new=mock.AsyncMock(return_value=(experiment, 3)),
        ) as prepare,
        mock.patch(
            "labnotes.runner.start_experiment.finalize_lost_runs",
            new=mock.AsyncMock(),
        ) as finalize,
        mock.patch(
            "labnotes.runner.start_experiment.run_experiment",
            new=mock.AsyncMock(return_value=results),
        ) as run,
        mock.patch(
            "labnotes.runner.start_experiment.project_snapshot"
        ) as project_snapshot,
    ):
        project_snapshot.return_value.__enter__.return_value = snapshot
        start = start_experiment(
            config,
            "exp",
            Path("other.toml"),
            3,
            30,
            {"model": ["small"]},
            ["--verbose"],
            "setup",
            "teardown",
            "labnotes experiments exp run",
            None,
            2,
            True,
        )
        assert asyncio.run(start(report, listen)) == results

    prepare.assert_awaited_once_with(
        config,
        "exp",
        Path("other.toml"),
        3,
        {"model": ["small"]},
        ["--verbose"],
        "setup",
        "teardown",
        2,
        True,
    )
    finalize.assert_awaited_once_with(config)
    project_snapshot.assert_called_once_with(config.root)
    run.assert_awaited_once_with(
        config,
        "exp",
        experiment,
        3,
        report,
        listen,
        timeout=30,
        only={"model": ["small"]},
        args=["--verbose"],
        snapshot=snapshot,
        command_line="labnotes experiments exp run",
        run_id=None,
        run_state=start.run_state,
    )


def test_invocation_keeps_its_journal_identity() -> None:
    config = mock.Mock(root=Path("/tmp/project"), runs="{experiment}/runs/{run}")
    start = start_experiment(config, "exp", None, None, None, None, None, None, None)
    original = start.run_state
    with pytest.raises(FrozenInstanceError):
        setattr(start, "run_state", mock.sentinel.other)
    assert start.run_state is original
