from labnotes.tui.config import RUN_COLUMNS


def test_lists_the_run_view_columns_in_order() -> None:
    assert RUN_COLUMNS == ("run", "params", "status", "time", "memory", "size")
