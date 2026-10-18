from labnotes.sql_quote import quote_identifier, quote_string


def experiment_runs(experiment: str, params: list[str]) -> str:
    columns = "".join(
        f", params ->> {quote_string(f'$.{quote_identifier(key)}')}"
        f" AS {quote_identifier(key)}"
        for key in params
    )
    return (
        f"(SELECT *{columns} FROM runs"
        f" WHERE experiment = {quote_string(experiment)})"
    )
