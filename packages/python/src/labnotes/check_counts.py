from dirsql import DirSQL


async def check_counts(
    tables: DirSQL, source: str, summary: dict[str, object]
) -> dict[str, object]:
    rule = str(summary["completed_run"])
    try:
        await tables.query(f"SELECT ({rule}) FROM {source} LIMIT 0")
    except RuntimeError as error:
        # A broken rule counts nothing, so the pages still render and say why.
        return {
            **summary,
            "completed_run": "0",
            "counts_error": f"{rule} doesn't work: {error}",
        }
    return summary
