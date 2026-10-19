import signal
import time

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Static

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
            lambda: None, lambda run: None, lambda count: None, lambda run: None
        )
        self.concurrency = 1
        self.done = False
        self.started: dict[str, float] = {}
        self.pending: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="runs", cursor_type="row")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        for column in COLUMNS:
            table.add_column(column, key=column)

    def on_ready(self) -> None:
        self.set_interval(1, self.tick)
        self.run_worker(self.drive())

    async def drive(self) -> None:
        self.results = await self.start(self.show_event, self.listen)
        self.done = True
        failed = sum(result["exit_code"] != 0 for result in self.results)
        passed = len(self.results) - failed
        self.show(f"{passed} passed, {failed} failed. q to quit.")

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
                    table.add_row(*map(dim, cells), key=planned["run"])
                    self.pending.add(planned["run"])
                self.show_concurrency(event)
                self.show(describe_event(event))
            case "started":
                self.pending.discard(run)
                self.started[run] = time.monotonic()
                args = " ".join(param_args(event["params"]))  # type: ignore[arg-type]
                cells = (run, args, "running", format_elapsed(0))
                for column, cell in zip(COLUMNS, cells):
                    table.update_cell(run, column, cell, update_width=True)
            case "ended":
                outcome = event["error"] or f"exited {event['exit_code']}"
                table.update_cell(run, "status", outcome, update_width=True)
                self.tick()
                del self.started[run]
            case "queued":
                self.reorder(event)
                table.move_cursor(row=table.get_row_index(run))
                self.show(describe_event(event))
            case "deselected":
                self.pending.discard(run)
                table.update_cell(run, "status", dim("deselected"))
                self.reorder(event)
                self.show(describe_event(event))
            case "reselected":
                self.pending.add(run)
                table.update_cell(run, "status", dim("pending"))
                self.reorder(event)
                self.show(describe_event(event))
            case "concurrency":
                self.show_concurrency(event)
                self.show(describe_event(event))
            case "stopping":
                for pending in self.pending:
                    table.update_cell(pending, "status", dim("skipped"))
                self.show(describe_event(event))
            case _:
                self.show(describe_event(event))

    def reorder(self, event: dict[str, object]) -> None:
        table = self.query_one(DataTable)
        waiting: list[str] = [*event["pending"], *event["held"]]  # type: ignore[misc]
        for run in waiting:
            row = table.get_row(run)
            table.remove_row(run)
            table.add_row(*row, key=run)

    def show_concurrency(self, event: dict[str, object]) -> None:
        self.concurrency = int(event["concurrency"])  # type: ignore[call-overload]
        self.sub_title = f"{self.concurrency} at a time"

    def tick(self) -> None:
        table = self.query_one(DataTable)
        for run, began in self.started.items():
            table.update_cell(
                run, "time", format_elapsed(time.monotonic() - began), update_width=True
            )

    def show(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def action_interrupt(self) -> None:
        if self.done:
            self.exit()
        else:
            self.controls.interrupt()

    async def action_quit(self) -> None:
        if self.done:
            self.exit()
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

    def action_concurrency(self, change: int) -> None:
        self.controls.set_concurrency(self.concurrency + change)
