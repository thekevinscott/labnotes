import json
from typing import cast

from dirsql import DirSQL

from labnotes.list_runs import list_runs
from labnotes.render_markdown import render_markdown
from labnotes.run_columns import run_columns
from labnotes.sql_quote import quote_string
from labnotes.study_progress import study_progress
from labnotes.summarize_design import summarize_design


async def load_experiment(
    experiments: DirSQL, runs: DirSQL, name: str
) -> dict[str, object] | None:
    found = await experiments.query(
        f"SELECT name, study, design FROM experiments WHERE name = {quote_string(name)}"
    )
    if not found:
        return None
    [row] = found
    notes = await experiments.query(
        "SELECT name, content FROM notes"
        f" WHERE experiment = {quote_string(name)} ORDER BY name"
    )
    summary = summarize_design(json.loads(str(row["design"])))
    varies = cast(dict[str, list[object]], summary["varies"])
    study = None if row["study"] is None else str(row["study"])
    columns = await run_columns(runs)
    progress = await study_progress(runs, study, summary, columns)
    listed = (
        []
        if study is None
        else await list_runs(runs, study, str(summary["completed_run"]))
    )
    return {
        "name": row["name"],
        "study": study,
        **summary,
        **progress,
        "notes": [
            {"name": note["name"], "html": render_markdown(str(note["content"]))}
            for note in notes
        ],
        "runs_list": listed,
        "run_columns": columns[:1] + [key for key in varies if key in columns[1:]],
    }
