import json
from typing import cast

from dirsql import DirSQL

from labnotes.check_counts import check_counts
from labnotes.count_runs import count_runs
from labnotes.experiment_runs import experiment_runs
from labnotes.summarize_config import summarize_config


async def list_experiments(tables: DirSQL, mode: str) -> list[dict[str, object]]:
    rows = await tables.query(
        "SELECT name, display_name, config FROM experiments ORDER BY name"
    )
    listed = []
    for row in rows:
        name = str(row["name"])
        config = None if row["config"] is None else json.loads(str(row["config"]))
        summary = summarize_config(config, mode)
        varies = cast(dict[str, list[object]], summary["varies"])
        source = experiment_runs(name, list(varies))
        summary = await check_counts(tables, source, summary)
        [totals] = await count_runs(tables, source, str(summary["completed_run"]))
        listed.append(
            {"name": name, "display_name": row["display_name"], **summary, **totals}
        )
    return listed
