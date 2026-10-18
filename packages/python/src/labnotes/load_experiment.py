import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

from dirsql import DirSQL

from labnotes.experiment_notes import experiment_notes
from labnotes.experiment_progress import experiment_progress
from labnotes.experiment_runs import experiment_runs
from labnotes.list_runs import list_runs
from labnotes.parse_run_view import parse_run_view
from labnotes.python_blocks import python_blocks
from labnotes.render_markdown import render_markdown
from labnotes.sort_href import sort_href
from labnotes.sql_quote import quote_string
from labnotes.summarize_config import summarize_config


def _no_outputs(note: str, content: str) -> Sequence[str]:
    return ()


async def load_experiment(
    tables: DirSQL,
    root: Path,
    name: str,
    params: Mapping[str, str],
    outputs_for: Callable[[str, str], Sequence[str]] = _no_outputs,
) -> dict[str, object] | None:
    found = await tables.query(
        "SELECT name, display_name, config FROM experiments"
        f" WHERE name = {quote_string(name)}"
    )
    if not found:
        return None
    [row] = found
    config = None if row["config"] is None else json.loads(str(row["config"]))
    summary = summarize_config(config)
    varies = cast(dict[str, list[object]], summary["varies"])
    source = experiment_runs(name, list(varies))
    progress = await experiment_progress(tables, source, summary)
    shown = ["id", *(key for key in varies if key != "id")]
    view = parse_run_view(params, shown)
    notes = await experiment_notes(tables, root, name)
    return {
        "name": row["name"],
        "display_name": row["display_name"],
        **summary,
        **progress,
        "notes": [
            {
                "name": note["name"],
                "html": render_markdown(
                    note["content"], outputs_for(note["name"], note["content"])
                ),
                "runnable": bool(python_blocks(note["content"])),
            }
            for note in notes
        ],
        "runs_list": await list_runs(
            tables, source, str(summary["completed_run"]), view
        ),
        "run_columns": shown,
        "run_view": view,
        "sort_hrefs": {
            column: sort_href(view, column) for column in ["status", *shown]
        },
    }
