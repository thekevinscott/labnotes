from pathlib import Path

from labnotes.list_experiments import list_experiments
from labnotes.open_experiments import open_experiments
from labnotes.open_runs import open_runs
from labnotes.scope_runs import scope_runs


async def query_experiment(
    experiments_folder: Path, data_folder: Path, name: str, sql: str | None
) -> object:
    experiments = open_experiments(experiments_folder)
    runs = open_runs(data_folder)
    await experiments.ready()
    await runs.ready()
    listed = await list_experiments(experiments, runs)
    experiment = next((row for row in listed if row["name"] == name), None)
    if experiment is None:
        raise LookupError(f"no experiment named {name!r}")
    if sql is None:
        return experiment
    if experiment["study"] is None:
        raise LookupError(f"{name!r} has no study in its design.yaml")
    return await runs.query(scope_runs(sql, str(experiment["study"])))
