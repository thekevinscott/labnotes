import json
from collections.abc import Callable, Mapping, Sequence
from typing import cast

from dirsql import DirSQL

from labnotes.list_runs import list_runs
from labnotes.parse_run_view import parse_run_view
from labnotes.render_markdown import render_markdown
from labnotes.run_columns import run_columns
from labnotes.sort_href import sort_href
from labnotes.sql_quote import quote_string
from labnotes.study_progress import study_progress
from labnotes.summarize_design import summarize_design


def _no_outputs(note: str, content: str) -> Sequence[str]:
    return ()


async def load_experiment(
    experiments: DirSQL,
    runs: DirSQL,
    name: str,
    params: Mapping[str, str],
    outputs_for: Callable[[str, str], Sequence[str]] = _no_outputs,
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
    shown = columns[:1] + [key for key in varies if key in columns[1:]]
    view = parse_run_view(params, shown)
    listed = (
        []
        if study is None
        else await list_runs(runs, study, str(summary["completed_run"]), view)
    )
    return {
        "name": row["name"],
        "study": study,
        **summary,
        **progress,
        "notes": [
            {
                "name": note["name"],
                "html": render_markdown(
                    str(note["content"]),
                    outputs_for(str(note["name"]), str(note["content"])),
                ),
            }
            for note in notes
        ],
        "runs_list": listed,
        "run_columns": shown,
        "run_view": view,
        "sort_hrefs": {
            column: sort_href(view, column) for column in ["status", *shown]
        },
    }
