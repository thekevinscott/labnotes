from labnotes.sql_quote import quote_identifier, quote_string

STARTED = "strftime('%Y-%m-%d %H:%M:%S', created)"
DURATION = "CAST(round((julianday(ended) - julianday(created)) * 86400) AS INTEGER)"


def experiment_runs(experiment: str, params: list[str]) -> str:
    columns = "".join(
        f", params ->> {quote_string(f'$.{quote_identifier(key)}')}"
        f" AS {quote_identifier(key)}"
        for key in params
    )
    return (
        f"(SELECT *{columns}, {STARTED} AS started, {DURATION} AS duration FROM runs"
        f" WHERE experiment = {quote_string(experiment)})"
    )
