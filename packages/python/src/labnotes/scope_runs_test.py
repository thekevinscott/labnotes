import pytest

from labnotes.scope_runs import scope_runs

RUNS = "runs AS (SELECT * FROM main.runs WHERE study = 's1')"


def test_scopes_runs_to_the_study() -> None:
    assert scope_runs("SELECT * FROM runs", "s1") == f"WITH {RUNS} SELECT * FROM runs"


def test_quotes_the_study() -> None:
    assert "study = 'it''s'" in scope_runs("SELECT 1", "it's")


@pytest.mark.parametrize(
    "sql",
    ["WITH x AS (SELECT 1) SELECT * FROM x", "  with\nx AS (SELECT 1) SELECT * FROM x"],
)
def test_joins_a_leading_with_clause(sql: str) -> None:
    assert scope_runs(sql, "s1") == f"WITH {RUNS}, x AS (SELECT 1) SELECT * FROM x"


def test_keeps_recursive_on_the_joined_clause() -> None:
    sql = "WITH RECURSIVE x(n) AS (SELECT 1) SELECT n FROM x"
    assert (
        scope_runs(sql, "s1")
        == f"WITH RECURSIVE {RUNS}, x(n) AS (SELECT 1) SELECT n FROM x"
    )


def test_needs_whitespace_after_with() -> None:
    assert scope_runs("WITHOUT", "s1") == f"WITH {RUNS} WITHOUT"
