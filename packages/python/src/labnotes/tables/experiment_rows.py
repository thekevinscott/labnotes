import json

from labnotes.models import LabnotesConfig
from labnotes.summarize_config import summarize_config
from labnotes.tables.list_experiment_runs import list_experiment_runs
from labnotes.tables.open_tables import open_tables
from labnotes.tables.summarize_experiments import summarize_experiments


async def experiment_rows(
    config: LabnotesConfig, name: str | None, action: str | None
) -> list[dict[str, object]] | None:
    tables = open_tables(config)
    rows = await summarize_experiments(tables, name)
    if name is not None and not rows:
        return None
    match name, action:
        case str(), "runs":
            [row] = rows
            stored = row["config"]
            summary = summarize_config(json.loads(str(stored)) if stored else None)
            return await list_experiment_runs(
                tables, name, str(summary["completed_run"])
            )
    return rows
