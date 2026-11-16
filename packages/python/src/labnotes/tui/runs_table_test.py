from unittest import mock

from labnotes.tui.runs_table import RunsTable


def test_binds_vim_keys_to_cursor_moves() -> None:
    bindings = [b for b in RunsTable.BINDINGS if not isinstance(b, tuple)]
    assert [(b.key, b.action, b.show) for b in bindings] == [
        ("j", "cursor_down", False),
        ("k", "cursor_up", False),
        ("g", "scroll_top", False),
        ("G", "scroll_bottom", False),
    ]


def test_drops_cached_rendering_before_measuring_new_rows() -> None:
    table = RunsTable()
    table._row_renderable_cache[(0, 0)] = mock.sentinel.renderables
    table._line_cache[mock.sentinel.key] = mock.sentinel.line
    cached_at_measure: list[tuple[int, int]] = []
    with mock.patch(
        "labnotes.tui.runs_table.DataTable._update_dimensions",
        side_effect=lambda rows: cached_at_measure.append(
            (len(table._row_renderable_cache), len(table._line_cache))
        ),
    ) as measure:
        table._update_dimensions(["a"])
    measure.assert_called_once_with(["a"])
    assert cached_at_measure == [(0, 0)]
