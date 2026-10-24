from labnotes.tui.invocation_columns import invocation_columns


def test_lists_a_status_column_then_the_run_columns() -> None:
    experiment = {"run_columns": ["id", "m", "started"], "run_groups": None}

    assert invocation_columns(experiment) == [
        {"key": "status", "label": ""},
        {"key": "id", "label": "id"},
        {"key": "m", "label": "m"},
        {"key": "started", "label": "started"},
    ]


def test_counts_runs_after_the_id_when_runs_are_grouped() -> None:
    experiment = {"run_columns": ["id", "m"], "run_groups": []}

    assert [column["key"] for column in invocation_columns(experiment)] == [
        "status",
        "id",
        "runs",
        "m",
    ]
    assert invocation_columns(experiment)[2] == {"key": "runs", "label": "runs"}
