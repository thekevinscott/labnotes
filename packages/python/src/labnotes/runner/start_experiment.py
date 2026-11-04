from dataclasses import dataclass
from pathlib import Path

from labnotes.models import LabnotesConfig, Listen, Report, Start
from labnotes.runner.finalize_lost_runs import finalize_lost_runs
from labnotes.runner.prepare_experiment import prepare_experiment
from labnotes.runner.project_snapshot import project_snapshot
from labnotes.runner.run_experiment import run_experiment
from labnotes.runner.run_state import RunState


@dataclass(frozen=True)
class ExperimentStart:
    """Keep a run invocation's journal path with its scheduler callback."""

    run_state: RunState
    start: Start

    async def __call__(self, report: Report, listen: Listen) -> list[dict[str, object]]:
        return await self.start(report, listen)


def start_experiment(
    config: LabnotesConfig,
    name: str,
    experiment_config: Path | None,
    concurrency: int | None,
    timeout: int | None,
    only: dict[str, list[str]] | None,
    args: list[str] | None,
    setup: str | None,
    teardown: str | None,
    command_line: str | None = None,
    run_id: str | None = None,
    retries: int | None = None,
    replace_capped: bool = False,
) -> ExperimentStart:
    state = RunState.create(config, name)

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        experiment, limit = await prepare_experiment(
            config,
            name,
            experiment_config,
            concurrency,
            only,
            args,
            setup,
            teardown,
            retries,
            replace_capped,
        )
        await finalize_lost_runs(config)
        with project_snapshot(config.root) as snapshot:
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
                snapshot=snapshot,
                command_line=command_line,
                run_id=run_id,
                run_state=state,
            )

    return ExperimentStart(state, start)
