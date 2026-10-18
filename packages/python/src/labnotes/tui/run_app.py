import signal
import time
from collections.abc import Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Static

from labnotes.models import Start
from labnotes.runner.describe_event import describe_event
from labnotes.runner.stop_then_kill import stop_then_kill
from labnotes.runner.param_args import param_args
from labnotes.tui.dim import dim
from labnotes.tui.format_elapsed import format_elapsed

COLUMNS = ("run", "params", "status", "time")


class RunApp(App[None]):
    BINDINGS = [
        Binding("ctrl+c", "interrupt", "Stop runs"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, start: Start, title: str) -> None:
        super().__init__()
        self.start = start
        self.title = title
        self.results: list[dict[str, object]] = []
        self.interrupt: Callable[[], None] = lambda: None
        self.done = False
        self.started: dict[str, float] = {}
        self.pending: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="runs", cursor_type="none")
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

    def listen(self, interrupt: Callable[[], None]) -> None:
        self.interrupt = interrupt
        stop_then_kill(interrupt, signal.SIGTERM, signal.SIGHUP)

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
                self.show(describe_event(event))
            case "started":
                self.pending.discard(run)
                self.started[run] = time.monotonic()
                args = " ".join(param_args(event["params"]))  # type: ignore[arg-type]
                cells = (run, args, "running", format_elapsed(0))
                for column, cell in zip(COLUMNS, cells, strict=True):
                    table.update_cell(run, column, cell, update_width=True)
            case "ended":
                outcome = event["error"] or f"exited {event['exit_code']}"
                table.update_cell(run, "status", outcome, update_width=True)
                self.tick()
                del self.started[run]
            case "stopping":
                for pending in self.pending:
                    table.update_cell(pending, "status", dim("skipped"))
                self.show(describe_event(event))
            case _:
                self.show(describe_event(event))

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
            self.interrupt()

    async def action_quit(self) -> None:
        if self.done:
            self.exit()
        else:
            self.show("Runs are still going. Ctrl-C stops them.")
