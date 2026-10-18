from dirsql import DirSQL

from labnotes.sql_quote import quote_string

SUMMARY = """
SELECT
  e.name,
  e.display_name,{config}
  (SELECT max(created) FROM runs WHERE runs.experiment = e.name) AS last_run,
  (
    SELECT min(t) FROM (
      SELECT ctime AS t FROM files WHERE files.experiment = e.name
      UNION ALL SELECT created FROM runs WHERE runs.experiment = e.name
    )
  ) AS created,
  (SELECT count(*) FROM files WHERE files.experiment = e.name) AS files,
  (SELECT count(*) FROM runs WHERE runs.experiment = e.name) AS runs
FROM experiments AS e
"""


async def summarize_experiments(
    tables: DirSQL, name: str | None = None
) -> list[dict[str, object]]:
    if name is None:
        return await tables.query(SUMMARY.format(config="") + " ORDER BY e.name")
    sql = SUMMARY.format(config=" e.config,")
    return await tables.query(f"{sql} WHERE e.name = {quote_string(name)}")
