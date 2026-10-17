from labnotes.models import LabnotesConfig
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
    if name is not None and action == "runs":
        return await list_experiment_runs(tables, name)
    return rows
