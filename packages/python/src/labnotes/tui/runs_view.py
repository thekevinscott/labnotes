from collections.abc import Awaitable, Callable
from typing import Any

from labnotes.tui.check_view_response import check_view_response

type Columns = list[dict[str, str]]
type Rows = dict[str, dict[str, Any]]
type Request = Callable[[dict[str, Any]], Awaitable[tuple[str, float]]]

SLOW_SECONDS = 0.1


class RunsView:
    """Track which runs the view worker must see again, and its last good answer."""

    def __init__(self, request: Request) -> None:
        self.request = request
        self.columns: Columns = []
        self.native: Rows = {}
        self.sent_columns: Columns | None = None
        self.sent: Rows = {}
        self.pending: set[str] = set()
        self.busy = False
        self.shown_columns: Columns | None = None
        self.shown: Rows = {}
        self.error: str | None = None
        self.elapsed: float | None = None

    def update(self, columns: Columns, native: Rows) -> None:
        if columns != self.sent_columns:
            self.pending |= native.keys()
        self.pending |= {f for f, row in native.items() if self.sent.get(f) != row}
        self.pending &= native.keys()
        self.sent = {f: row for f, row in self.sent.items() if f in native}
        self.shown = {f: row for f, row in self.shown.items() if f in native}
        self.columns, self.native = columns, native

    def touch(self, path: str) -> None:
        owners = [f for f in self.native if path.startswith(f"{f}/")]
        if owners:
            self.pending.add(max(owners, key=len))

    def next_request(self) -> dict[str, Any] | None:
        if self.busy or not self.pending:
            return None
        rows = {folder: self.native[folder] for folder in sorted(self.pending)}
        self.pending = set()
        self.busy = True
        self.sent_columns = self.columns
        self.sent.update(rows)
        return {"columns": self.columns, "rows": rows}

    async def exchange(self, request: dict[str, Any]) -> bool:
        """Send a request and keep a valid answer; report whether rows changed."""
        try:
            reply, self.elapsed = await self.request(request)
            columns, rows = check_view_response(reply, request)
        except (ValueError, OSError) as error:
            self.error = str(error)
            return False
        finally:
            self.busy = False
        changed = columns != self.shown_columns or any(
            self.shown.get(folder) != row for folder, row in rows.items()
        )
        self.error = None
        self.shown_columns = columns
        self.shown.update(rows)
        return changed

    def table(self) -> tuple[Columns, Rows]:
        rows = {f: self.shown.get(f, row) for f, row in self.native.items()}
        return self.columns if self.shown_columns is None else self.shown_columns, rows

    def status(self) -> str:
        notes = []
        if self.error is not None:
            notes.append(f"runs view: {self.error}")
        if self.elapsed is not None and self.elapsed > SLOW_SECONDS:
            notes.append(f"runs view took {round(self.elapsed * 1000)} ms")
        return " · ".join(notes)
