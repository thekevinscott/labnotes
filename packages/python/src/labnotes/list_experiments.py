import json

from dirsql import DirSQL

from labnotes.run_columns import run_columns
from labnotes.study_progress import study_progress
from labnotes.summarize_design import summarize_design


async def list_experiments(
    experiments: DirSQL, runs: DirSQL
) -> list[dict[str, object]]:
    rows = await experiments.query(
        "SELECT name, study, design FROM experiments ORDER BY name"
    )
    columns = await run_columns(runs)
    listed = []
    for row in rows:
        summary = summarize_design(json.loads(str(row["design"])))
        study = None if row["study"] is None else str(row["study"])
        progress = await study_progress(runs, study, summary, columns)
        listed.append({"name": row["name"], "study": study, **summary, **progress})
    return listed
