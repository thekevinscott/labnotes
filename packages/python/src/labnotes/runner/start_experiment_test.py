import asyncio
from pathlib import Path
from unittest import mock

from labnotes.runner.start_experiment import start_experiment


def test_prepares_and_runs_in_this_process_after_finalizing_lost_runs() -> None:
    config = mock.Mock()
    experiment = mock.sentinel.experiment
    report = mock.Mock()
    listen = mock.Mock()
    results = [{"exit_code": 0}]
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
    ):
        start = start_experiment(
            config,
            "exp",
            Path("other.toml"),
            3,
            30,
            {"model": "small"},
            ["--verbose"],
            "setup",
            "teardown",
        )
        assert asyncio.run(start(report, listen)) == results

    prepare.assert_awaited_once_with(
        config,
        "exp",
        Path("other.toml"),
        3,
        {"model": "small"},
        ["--verbose"],
        "setup",
        "teardown",
    )
    finalize.assert_awaited_once_with(config)
    run.assert_awaited_once_with(
        config,
        "exp",
        experiment,
        3,
        report,
        listen,
        timeout=30,
        only={"model": "small"},
        args=["--verbose"],
    )
