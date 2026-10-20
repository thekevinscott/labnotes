import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from dirsql import DirSQL

from labnotes.check_counts import check_counts
from labnotes.count_groups import count_groups
from labnotes.count_runs import count_runs
from labnotes.experiment_notes import experiment_notes
from labnotes.experiment_runs import experiment_runs
from labnotes.format_value import format_value
from labnotes.group_runs import group_runs
from labnotes.list_runs import list_runs
from labnotes.models import QueryParams
from labnotes.nests_runs import nests_runs
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
    mode: str,
    name: str,
    params: QueryParams,
    outputs_for: Callable[[str, str], Sequence[str]] = _no_outputs,
) -> dict[str, object] | None:
    found = await tables.query(
        "SELECT name, display_name, config, source FROM experiments"
        f" WHERE name = {quote_string(name)}"
    )
    if not found:
        return None
    [row] = found
    config = None if row["config"] is None else json.loads(str(row["config"]))
    summary = summarize_config(config, mode)
    varies = cast(dict[str, list[object]], summary["varies"])
    source = experiment_runs(name, list(varies))
    summary = await check_counts(tables, source, summary)
    shown = ["id", *(key for key in varies if key != "id"), "started", "duration"]
    choices = {
        key: {format_value(value): json.dumps(value) for value in values}
        for key, values in varies.items()
        if key != "id"
    }
    view = parse_run_view(params, shown, choices)
    [totals] = await count_runs(tables, source, str(summary["completed_run"]))
    notes = await experiment_notes(tables, root, name)
    runs = await list_runs(tables, source, str(summary["completed_run"]), view)
    nested = summary["mode"] == "adhoc" and await nests_runs(tables, source)
    keys = [key for key in varies if key != "id"]
    groups = (
        group_runs(runs, keys, await count_groups(tables, source)) if nested else None
    )
    return {
        "name": row["name"],
        "display_name": row["display_name"],
        "config_source": row["source"],
        "counts_set": "counts" in (config or {}),
        **summary,
        **totals,
        "notes": [
            {
                "name": note["name"],
                "content": note["content"],
                "html": render_markdown(
                    note["content"], outputs_for(note["name"], note["content"])
                ),
                "runnable": bool(python_blocks(note["content"])),
            }
            for note in notes
        ],
        "runs_list": runs,
        "run_groups": groups,
        "run_columns": shown,
        "run_view": view,
        "run_choices": choices,
        "sort_hrefs": {
            column: sort_href(view, column) for column in ["status", *shown]
        },
    }
