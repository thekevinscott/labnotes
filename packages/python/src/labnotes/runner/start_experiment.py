from pathlib import Path

from labnotes.models import LabnotesConfig, Listen, Report, Start
from labnotes.runner.finalize_lost_runs import finalize_lost_runs
from labnotes.runner.prepare_experiment import prepare_experiment
from labnotes.runner.run_experiment import run_experiment


def start_experiment(
    config: LabnotesConfig,
    name: str,
    experiment_config: Path | None,
    concurrency: int | None,
    timeout: int | None,
    only: dict[str, str] | None,
    args: list[str] | None,
    setup: str | None,
    teardown: str | None,
) -> Start:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        experiment, limit = await prepare_experiment(
            config, name, experiment_config, concurrency, only, args, setup, teardown
        )
        await finalize_lost_runs(config)
        return await run_experiment(
            config,
            name,
            experiment,
            limit,
            report,
            listen,
            timeout=timeout,
            only=only,
            args=args,
        )

    return start
