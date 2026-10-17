import re

from labnotes.sql_quote import quote_string

LEADING_WITH = re.compile(r"\s*WITH(\s+RECURSIVE)?\s+", re.IGNORECASE)


def scope_runs(sql: str, study: str) -> str:
    runs = f"runs AS (SELECT * FROM main.runs WHERE study = {quote_string(study)})"
    leading_with = LEADING_WITH.match(sql)
    if leading_with is None:
        return f"WITH {runs} {sql}"
    recursive = " RECURSIVE" if leading_with.group(1) else ""
    return f"WITH{recursive} {runs}, {sql[leading_with.end() :]}"
