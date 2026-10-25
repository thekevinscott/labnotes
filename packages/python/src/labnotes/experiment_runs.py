import warnings

from labnotes.sql_quote import quote_identifier, quote_string
from labnotes.tables.runs_columns import runs_columns

STARTED = "strftime('%Y-%m-%d %H:%M:%S', created)"
DURATION = "CAST(round((julianday(ended) - julianday(created)) * 86400) AS INTEGER)"


def experiment_runs(experiment: str, params: list[str]) -> str:
    taken = {*runs_columns(), "started", "duration"}
    clashes = [key for key in params if key in taken]
    if clashes:
        warnings.warn(
            f"Params {', '.join(clashes)} clash with runs columns;"
            " the runs column wins. Read them from params instead.",
            stacklevel=2,
        )
    columns = "".join(
        f", params ->> {quote_string(f'$.{quote_identifier(key)}')}"
        f" AS {quote_identifier(key)}"
        for key in params
        if key not in taken
    )
    return (
        f"(SELECT *{columns}, {STARTED} AS started, {DURATION} AS duration FROM runs"
        f" WHERE experiment = {quote_string(experiment)})"
    )
