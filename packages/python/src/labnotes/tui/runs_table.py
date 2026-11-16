from collections.abc import Iterable

from textual.binding import Binding
from textual.widgets import DataTable
from textual.widgets.data_table import RowKey


class RunsTable(DataTable[object]):
    BINDINGS = [
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("g", "scroll_top", show=False),
        Binding("G", "scroll_bottom", show=False),
    ]

    def _update_dimensions(self, new_rows: Iterable[RowKey]) -> None:
        # Textual measures labels from a cache that a paint after clear() can
        # fill with label-less rows, leaving the label column zero wide.
        self._row_renderable_cache.clear()
        super()._update_dimensions(new_rows)
