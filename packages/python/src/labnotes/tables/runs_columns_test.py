from labnotes.tables.runs_columns import runs_columns


def test_names_every_column_the_runs_table_declares() -> None:
    assert runs_columns() == (
        "experiment",
        "id",
        "folder",
        "created",
        "ended",
        "exit_code",
        "error",
        "stdout",
        "stderr",
        "params",
        "meta",
        "command",
        "run",
    )


def test_reads_the_ddl_once() -> None:
    assert runs_columns() is runs_columns()
