from pathlib import Path

from labnotes.list_experiments import list_experiments
from labnotes.open_experiments import open_experiments
from labnotes.open_runs import open_runs


async def dump_experiments(
    experiments_folder: Path, data_folder: Path
) -> list[dict[str, object]]:
    experiments = open_experiments(experiments_folder)
    runs = open_runs(data_folder)
    await experiments.ready()
    await runs.ready()
    return await list_experiments(experiments, runs)
