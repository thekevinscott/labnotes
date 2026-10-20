from labnotes.tui.runs_table import RunsTable


def test_binds_vim_keys_to_cursor_moves() -> None:
    bindings = [b for b in RunsTable.BINDINGS if not isinstance(b, tuple)]
    assert [(b.key, b.action, b.show) for b in bindings] == [
        ("j", "cursor_down", False),
        ("k", "cursor_up", False),
        ("g", "scroll_top", False),
        ("G", "scroll_bottom", False),
    ]
