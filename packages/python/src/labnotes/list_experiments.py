import json
from typing import cast

from dirsql import DirSQL

from labnotes.experiment_progress import experiment_progress
from labnotes.experiment_runs import experiment_runs
from labnotes.summarize_config import summarize_config


async def list_experiments(tables: DirSQL) -> list[dict[str, object]]:
    rows = await tables.query(
        "SELECT name, display_name, config FROM experiments ORDER BY name"
    )
    listed = []
    for row in rows:
        name = str(row["name"])
        config = None if row["config"] is None else json.loads(str(row["config"]))
        summary = summarize_config(config)
        varies = cast(dict[str, list[object]], summary["varies"])
        source = experiment_runs(name, list(varies))
        progress = await experiment_progress(tables, source, summary)
        listed.append(
            {"name": name, "display_name": row["display_name"], **summary, **progress}
        )
    return listed
