import signal
import time

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Input, Static

from labnotes.models import Controls, Start
from labnotes.runner.describe_event import describe_event
from labnotes.runner.stop_then_kill import stop_then_kill
from labnotes.runner.param_args import param_args
from labnotes.tui.dim import dim
from labnotes.tui.format_elapsed import format_elapsed

COLUMNS = ("run", "params", "status", "time")


class RunApp(App[None]):
    BINDINGS = [
        Binding("ctrl+c", "interrupt", "Stop runs"),
        Binding("n", "run_next", "Run next"),
        Binding("d", "toggle_run", "Deselect"),
        Binding("D", "deselect_shown", "Deselect shown"),
        Binding("k", "kill_run", "Stop run"),
        Binding("h", "hide_failed", "Hide failed"),
        Binding("r", "retry", "Retry"),
        Binding("slash", "filter", "Filter", key_display="/"),
        Binding("escape", "clear_filter", "Clear filter"),
        Binding("plus,equals_sign", "concurrency(1)", "More at once", key_display="+"),
        Binding("minus", "concurrency(-1)", "Fewer at once", key_display="-"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, start: Start, title: str) -> None:
        super().__init__()
        self.start = start
        self.title = title
        self.results: list[dict[str, object]] = []
        self.controls = Controls(
            lambda: None,
            lambda run: None,
            lambda count: None,
            lambda run: None,
            lambda run: None,
            lambda run: None,
            lambda: None,
        )
        self.concurrency = 1
        self.idle = False
        self.next_run: str | None = None
        self.ended: set[str] = set()
        self.started: dict[str, float] = {}
        self.pending: set[str] = set()
        self.cells: dict[str, list[object]] = {}
        self.filter = ""
        self.failed: set[str] = set()
        self.hiding = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="runs", cursor_type="row")
        yield Input(id="filter", placeholder="Filter params")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        for column in COLUMNS:
            table.add_column(column, key=column)
        self.query_one(Input).display = False

    def on_ready(self) -> None:
        self.set_interval(1, self.tick)
        self.run_worker(self.drive())

    async def drive(self) -> None:
        self.results = await self.start(self.show_event, self.listen)
        self.exit()

    def listen(self, controls: Controls) -> None:
        self.controls = controls
        stop_then_kill(self.action_interrupt, signal.SIGTERM, signal.SIGHUP)

    def show_event(self, event: dict[str, object]) -> None:
        table = self.query_one(DataTable)
        run = str(event.get("run"))
        match event["event"]:
            case "planned":
                for planned in event["runs"]:  # type: ignore[attr-defined]
                    args = " ".join(param_args(planned["params"]))
                    cells = (planned["run"], args, "pending", "")
                    self.cells[planned["run"]] = [*map(dim, cells)]
                    self.pending.add(planned["run"])
                self.redraw(table.cursor_row)
                self.show_concurrency(event)
                self.show(describe_event(event))
            case "started":
                self.idle = False
                self.pending.discard(run)
                self.started[run] = time.monotonic()
                if run == self.next_run:
                    self.show("")
                args = " ".join(param_args(event["params"]))  # type: ignore[arg-type]
                cells = (run, args, "running", format_elapsed(0))
                for column, cell in zip(COLUMNS, cells):
                    self.set_cell(run, column, cell)
            case "ended":
                outcome = event["error"] or f"exited {event['exit_code']}"
                style = "red" if event["error"] or event["exit_code"] else ""
                if style:
                    self.failed.add(run)
                self.ended.add(run)
                self.set_cell(run, "status", Text(str(outcome), style=style))
                self.tick()
                del self.started[run]
                self.redraw(table.cursor_row)
            case "queued":
                self.reorder(event, table.cursor_row)
                table.move_cursor(row=table.get_row_index(run))
                self.show(describe_event(event))
                self.next_run = run
            case "deselected":
                self.pending.discard(run)
                self.set_cell(run, "status", dim("deselected"))
                self.reorder(event, table.cursor_row)
                self.show(describe_event(event))
            case "reselected":
                self.pending.add(run)
                self.set_cell(run, "status", dim("pending"))
                self.reorder(event, table.cursor_row)
                self.show(describe_event(event))
            case "retried":
                again = str(event["retry"])
                args = " ".join(param_args(event["params"]))  # type: ignore[arg-type]
                self.cells[again] = [*map(dim, (again, args, "pending", ""))]
                self.pending.add(again)
                self.redraw(table.cursor_row)
                self.show(describe_event(event))
            case "idle":
                self.idle = True
                failed = len(self.failed)
                passed = len(self.ended) - failed
                self.show(f"{passed} passed, {failed} failed. q to quit.")
            case "concurrency":
                self.show_concurrency(event)
                self.show(describe_event(event))
            case "stopping":
                for pending in self.pending:
                    self.set_cell(pending, "status", dim("skipped"))
                self.show(describe_event(event))
            case _:
                self.show(describe_event(event))

    def reorder(self, event: dict[str, object], row: int) -> None:
        waiting: list[str] = [*event["pending"], *event["held"]]  # type: ignore[misc]
        for run in waiting:
            self.cells[run] = self.cells.pop(run)
        self.redraw(row)

    def redraw(self, row: int) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for run, cells in self.cells.items():
            hidden = self.hiding and run in self.failed
            if self.filter in str(cells[1]) and not hidden:
                table.add_row(*cells, key=run)
        table.move_cursor(row=row)

    def set_cell(self, run: str, column: str, cell: object) -> None:
        self.cells[run][COLUMNS.index(column)] = cell
        table = self.query_one(DataTable)
        if run in table.rows:
            table.update_cell(run, column, cell, update_width=True)

    def show_concurrency(self, event: dict[str, object]) -> None:
        self.concurrency = int(event["concurrency"])  # type: ignore[call-overload]
        self.sub_title = f"{self.concurrency} at a time"

    def tick(self) -> None:
        for run, began in self.started.items():
            self.set_cell(run, "time", format_elapsed(time.monotonic() - began))

    def show(self, text: str) -> None:
        self.next_run = None
        self.query_one("#status", Static).update(text)

    def action_interrupt(self) -> None:
        if self.idle:
            self.controls.finish()
        else:
            self.controls.interrupt()

    async def action_quit(self) -> None:
        if self.idle:
            self.controls.finish()
        else:
            self.show("Runs are still going. Ctrl-C stops them.")

    def cursor_run(self) -> str | None:
        table = self.query_one(DataTable)
        if not table.row_count:
            return None
        cell = table.coordinate_to_cell_key(table.cursor_coordinate)
        return str(cell.row_key.value)

    def action_run_next(self) -> None:
        if (run := self.cursor_run()) is not None:
            self.controls.run_next(run)

    def action_toggle_run(self) -> None:
        if (run := self.cursor_run()) is not None:
            self.controls.toggle(run)

    def action_hide_failed(self) -> None:
        self.hiding = not self.hiding
        self.redraw(self.query_one(DataTable).cursor_row)
        self.show("Failed runs hidden." if self.hiding else "Failed runs shown.")

    def action_retry(self) -> None:
        if (run := self.cursor_run()) is not None and run in self.failed:
            self.controls.retry(run)

    def action_kill_run(self) -> None:
        if (run := self.cursor_run()) is not None:
            self.controls.kill(run)

    def action_deselect_shown(self) -> None:
        shown = [str(key.value) for key in self.query_one(DataTable).rows]
        for run in shown:
            if run in self.pending:
                self.controls.toggle(run)

    def action_concurrency(self, change: int) -> None:
        self.controls.set_concurrency(self.concurrency + change)

    def action_filter(self) -> None:
        field = self.query_one(Input)
        field.display = True
        field.focus()

    def action_clear_filter(self) -> None:
        field = self.query_one(Input)
        field.value = ""
        field.display = False
        self.query_one(DataTable).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self.filter = event.value
        self.redraw(self.query_one(DataTable).cursor_row)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.input.display = bool(event.value)
        self.query_one(DataTable).focus()
