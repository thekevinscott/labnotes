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
        # A paint between clear() and this idle pass caches label-less rows,
        # which Textual then measures and redraws from: labels stay blank.
        self._clear_caches()
        super()._update_dimensions(new_rows)
