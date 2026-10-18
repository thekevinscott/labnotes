from labnotes.sql_quote import quote_string


def study_runs(study: str) -> str:
    return f"(SELECT * FROM runs WHERE study = {quote_string(study)})"
