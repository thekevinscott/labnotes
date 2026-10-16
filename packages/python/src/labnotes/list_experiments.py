from pathlib import Path

from labnotes.open_experiments import open_experiments
from labnotes.open_runs import open_runs


async def list_experiments(
    experiments_folder: Path, data_folder: Path
) -> list[dict[str, object]]:
    experiments = open_experiments(experiments_folder)
    runs = open_runs(data_folder)
    await experiments.ready()
    await runs.ready()
    rows = await experiments.query("SELECT name, study FROM experiments ORDER BY name")
    counts = await runs.query("SELECT study, COUNT(*) AS n FROM runs GROUP BY study")
    runs_by_study = {count["study"]: count["n"] for count in counts}
    return [{**row, "runs": runs_by_study.get(row["study"], 0)} for row in rows]
