import asyncio
import signal
import time
from functools import partial
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Input, Static

from labnotes.format_bytes import format_bytes
from labnotes.models import Controls, Start
from labnotes.retries import RETRY_EXIT_CODE
from labnotes.run_usage import run_usage
from labnotes.runner.describe_event import describe_event
from labnotes.runner.stop_then_kill import GRACE_SECONDS, stop_then_kill
from labnotes.runner.param_args import param_args
from labnotes.tui.dim import dim
from labnotes.tui.format_elapsed import format_elapsed
from labnotes.tui.leave_prompt import LeavePrompt
from labnotes.tui.log_blocks import LogBlocks
from labnotes.tui.run_output import RunOutput
from labnotes.tui.runs_table import RunsTable

COLUMNS = ("run", "params", "status", "time", "memory", "size")
PENDING, PASSED, FAILED = "○", "✓", "✗"
SPINNER = "|/-\\"
SKIPPED, DESELECTED = "–", "⊘"
VIEWING_ACTIONS = {"leave", "quit", "interrupt", "command_palette"}
GRABBED_ACTIONS = {"shift", "drop", "put_back"}
GRABBING_ACTIONS = {*GRABBED_ACTIONS, "grab", "quit", "interrupt", "command_palette"}


class RunApp(App[None]):
    CSS = "#concurrency { dock: right; width: auto; padding: 0 1; }"
    BINDINGS = [
        Binding("ctrl+c", "interrupt", "Quit"),
        Binding("n", "run_next", "Run next"),
        Binding("m", "grab", "Move"),
        Binding("j,down", "shift(1)", priority=True),
        Binding("k,up", "shift(-1)", priority=True),
        Binding("enter", "drop", "Drop", priority=True),
        Binding("escape", "put_back", "Put back"),
        Binding("space", "toggle_run", "Deselect"),
        Binding("D", "deselect_shown", "Deselect shown"),
        Binding("x", "kill_run", "Stop run"),
        Binding("f", "hide_failed", "Hide failed"),
        Binding("r", "retry", "Retry"),
        Binding("slash", "filter", "Filter", key_display="/"),
        Binding("escape", "leave", "Back"),
        Binding("plus,equals_sign", "concurrency(1)", "More at once", key_display="+"),
        Binding("minus", "concurrency(-1)", "Fewer at once", key_display="-"),
    ]

    def __init__(self, start: Start, title: str) -> None:
        super().__init__()
        self.start = start
        self.title = title
        self.results: list[dict[str, object]] = []
        self.error: Exception | None = None
        self.controls = Controls(
            lambda: None,
            lambda run: None,
            lambda count: None,
            lambda run: None,
            lambda run: None,
            lambda run: None,
            lambda: None,
            lambda run, place: None,
        )
        self.concurrency = 1
        self.idle = False
        self.next_run: str | None = None
        self.ended: set[str] = set()
        self.frame = 0
        self.started: dict[str, float] = {}
        self.pending: set[str] = set()
        self.cells: dict[str, list[object]] = {}
        self.filter = ""
        self.failed: set[str] = set()
        self.retried: set[str] = set()
        self.waiting: dict[str, float] = {}
        self.hiding = False
        self.folders: dict[str, Path] = {}
        self.viewing: str | None = None
        self.grabbed: str | None = None
        self.grabbed_from: list[str] = []
        self.sampling = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield RunsTable(id="runs", cursor_type="row")
        yield LogBlocks(id="blocks")
        yield RunOutput(id="output")
        yield Input(id="filter", placeholder="Filter params")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        for column in COLUMNS:
            table.add_column(column, key=column)
        self.query_one(Input).display = False
        self.query_one(RunOutput).display = False
        self.query_one(Header).mount(Static(id="concurrency"))
        table.set_interval(0.1, self.spin)

    def on_ready(self) -> None:
        self.set_interval(1, self.tick)
        self.set_interval(0.25, self.follow)
        self.run_worker(self.drive())

    async def drive(self) -> None:
        try:
            self.results = await self.start(self.show_event, self.listen)
        except Exception as error:
            self.error = error
        self.exit()

    def listen(self, controls: Controls) -> None:
        self.controls = controls
        stop_then_kill(self.stop_runs, signal.SIGTERM)
        asyncio.get_running_loop().add_signal_handler(signal.SIGHUP, self.exit)

    def show_event(self, event: dict[str, object]) -> None:
        table = self.query_one(DataTable)
        run = str(event.get("run"))
        match event["event"]:
            case "planned":
                self.title = str(event["title"])
                for planned in event["runs"]:  # type: ignore[attr-defined]
                    args = " ".join(param_args(planned["params"]))
                    cells = (
                        planned["run"].rpartition("/")[2],
                        args,
                        PENDING,
                        "",
                        "",
                        "",
                    )
                    self.cells[planned["run"]] = [*map(dim, cells)]
                    self.pending.add(planned["run"])
                self.redraw(table.cursor_row)
                self.show_concurrency(event)
                match event["mode"], event["runs"]:
                    case "adhoc", [only]:
                        self.view(only["run"])  # type: ignore[index]
            case "started":
                if run == self.grabbed:
                    self.action_put_back()
                self.idle = False
                self.pending.discard(run)
                self.started[run] = time.monotonic()
                self.folders[run] = Path(str(event["folder"]))
                if run == self.next_run:
                    self.show("")
                args = " ".join(param_args(event["params"]))  # type: ignore[arg-type]
                cells = (
                    run.rpartition("/")[2],
                    args,
                    SPINNER[self.frame],
                    format_elapsed(0),
                )
                for column, cell in zip(COLUMNS, cells):
                    self.set_cell(run, column, cell)
            case "ended":
                outcome = PASSED
                style = ""
                if event["error"] or event["exit_code"]:
                    reason = event["error"] or f"exited {event['exit_code']}"
                    outcome = f"{FAILED} {reason}"
                    style = "red"
                    self.failed.add(run)
                self.ended.add(run)
                self.set_cell(run, "status", Text(str(outcome), style=style))
                self.tick()
                del self.started[run]
                self.redraw(table.cursor_row)
                self.run_worker(partial(self.measure, run))
            case "queued":
                self.reposition(event, run)
                self.next_run = run
            case "moved":
                self.reposition(event, run)
            case "deselected":
                self.pending.discard(run)
                self.set_cell(run, "status", dim(DESELECTED))
                self.reorder(event, table.cursor_row)
                self.show(describe_event(event))
            case "reselected":
                self.pending.add(run)
                self.set_cell(run, "status", dim(PENDING))
                self.reorder(event, table.cursor_row)
                self.show(describe_event(event))
            case "retrying":
                self.waiting[run] = time.monotonic() + float(event["seconds"])  # type: ignore[arg-type]
                self.tick()
                self.show(describe_event(event))
            case "gave up":
                gave_up = f"{FAILED} gave up (exit {RETRY_EXIT_CODE})"
                self.set_cell(run, "status", Text(gave_up, style="red"))
                self.show(describe_event(event))
            case "retry cancelled":
                del self.waiting[run]
                outcome = f"{FAILED} exited {RETRY_EXIT_CODE}"
                self.set_cell(run, "status", Text(outcome, style="red"))
                self.show(describe_event(event))
            case "retried":
                if self.waiting.pop(run, None) is not None:
                    outcome = f"{FAILED} exited {RETRY_EXIT_CODE}, retried"
                    self.set_cell(run, "status", Text(outcome, style="red"))
                self.retried.add(run)
                again = str(event["retry"])
                args = " ".join(param_args(event["params"]))  # type: ignore[arg-type]
                self.cells[again] = [
                    *map(dim, (again.rpartition("/")[2], args, PENDING, "", "", ""))
                ]
                self.pending.add(again)
                self.redraw(table.cursor_row)
                self.show(describe_event(event))
            case "idle":
                self.idle = True
                self.show_summary()
            case "concurrency":
                self.show_concurrency(event)
            case "stopping":
                for pending in self.pending:
                    self.set_cell(pending, "status", dim(SKIPPED))
                self.show(describe_event(event))
            case _:
                self.show(describe_event(event))

    def show_summary(self) -> None:
        retried = len(self.retried)
        failed = len(self.failed - self.retried)
        passed = len(self.ended) - failed - retried
        again = f" {retried} retried." if retried else ""
        self.show(f"{passed} passed, {failed} failed.{again} Ctrl-C to quit.")

    def reposition(self, event: dict[str, object], run: str) -> None:
        table = self.query_one(DataTable)
        self.reorder(event, table.cursor_row)
        table.move_cursor(row=table.get_row_index(run))
        self.show(describe_event(event))

    def reorder(self, event: dict[str, object], row: int) -> None:
        self.release()
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

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        if isinstance(self.screen, LeavePrompt):
            return False
        if self.grabbed is not None:
            return action in GRABBING_ACTIONS
        if action in GRABBED_ACTIONS:
            return False
        return self.viewing is None or action in VIEWING_ACTIONS

    def show_concurrency(self, event: dict[str, object]) -> None:
        self.concurrency = int(event["concurrency"])  # type: ignore[call-overload]
        self.query_one("#concurrency", Static).update(f"{self.concurrency} at a time")

    def tick(self) -> None:
        now = time.monotonic()
        for run, began in self.started.items():
            self.set_cell(run, "time", format_elapsed(now - began))
        for run, due in self.waiting.items():
            wait = format_elapsed(max(0, due - now))
            outcome = f"{FAILED} exited {RETRY_EXIT_CODE}, retry in {wait}"
            self.set_cell(run, "status", Text(outcome, style="yellow"))
        if self.started and not self.sampling:
            self.sampling = True
            self.run_worker(self.sample)

    async def sample(self) -> None:
        try:
            for run in list(self.started):
                usage = await run_usage(self.folders[run], True)
                if run in self.started:
                    self.show_usage(run, usage)
        finally:
            self.sampling = False

    async def measure(self, run: str) -> None:
        self.show_usage(run, await run_usage(self.folders[run], False))

    def show_usage(self, run: str, usage: dict[str, int | None]) -> None:
        self.set_cell(run, "memory", format_bytes(usage["memory"]))
        self.set_cell(run, "size", format_bytes(usage["size"]))

    def spin(self) -> None:
        self.frame = (self.frame + 1) % len(SPINNER)
        for run in self.started:
            self.set_cell(run, "status", SPINNER[self.frame])

    def show(self, text: str) -> None:
        self.next_run = None
        self.query_one("#status", Static).update(text)

    def stop_runs(self) -> None:
        if self.idle:
            self.controls.finish()
        else:
            self.controls.interrupt()

    def action_interrupt(self) -> None:
        if self.started:
            self.push_screen(LeavePrompt(len(self.started)), self.answer)
        elif self.idle:
            self.controls.finish()
        else:
            self.exit()

    async def action_quit(self) -> None:
        self.action_interrupt()

    def answer(self, choice: str | None) -> None:
        if choice == "leave":
            self.exit()
        elif choice == "stop":
            self.controls.interrupt()
            self.set_timer(GRACE_SECONDS, self.controls.interrupt)

    def cursor_run(self) -> str | None:
        table = self.query_one(DataTable)
        if not table.row_count:
            return None
        cell = table.coordinate_to_cell_key(table.cursor_coordinate)
        return str(cell.row_key.value)

    def action_run_next(self) -> None:
        if (run := self.cursor_run()) is not None:
            self.controls.run_next(run)

    def queue(self) -> list[str]:
        return [run for run in self.cells if run in self.pending]

    def action_grab(self) -> None:
        if self.grabbed is not None:
            self.action_drop()
            return
        run = self.cursor_run()
        if run not in self.pending:
            return
        self.grabbed = run
        self.grabbed_from = list(self.cells)
        self.refresh_bindings()
        self.show(f"Moving {run}. j/k moves it, Enter drops it, Escape puts it back.")

    def action_shift(self, step: int) -> None:
        run = str(self.grabbed)
        queue = self.queue()
        place = queue.index(run) + step
        if place not in range(len(queue)):
            return
        order = list(self.cells)
        here, there = order.index(run), order.index(queue[place])
        order[here], order[there] = order[there], order[here]
        self.cells = {key: self.cells[key] for key in order}
        self.redraw_on(run)

    def action_drop(self) -> None:
        run = str(self.grabbed)
        self.release()
        self.show("")
        self.controls.move(run, self.queue().index(run))

    def action_put_back(self) -> None:
        run = str(self.grabbed)
        self.release()
        places = {key: place for place, key in enumerate(self.grabbed_from)}
        ordered = sorted(self.cells, key=lambda key: places.get(key, len(places)))
        self.cells = {key: self.cells[key] for key in ordered}
        self.redraw_on(run)
        self.show("")

    def release(self) -> None:
        self.grabbed = None
        self.refresh_bindings()

    def redraw_on(self, run: str) -> None:
        table = self.query_one(DataTable)
        self.redraw(table.cursor_row)
        table.move_cursor(row=table.get_row_index(run))

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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self.grabbed is None:
            self.view(str(event.row_key.value))

    def view(self, run: str) -> None:
        self.viewing = run
        self.query_one(LogBlocks).reset()
        self.query_one(RunOutput).reset()
        self.query_one(DataTable).display = False
        self.query_one(RunOutput).display = True
        self.sub_title = run
        self.show("")
        self.refresh_bindings()
        self.follow()

    def follow(self) -> None:
        if self.viewing in self.folders:
            self.query_one(LogBlocks).follow(self.folders[self.viewing])
            self.query_one(RunOutput).follow(self.folders[self.viewing])

    def action_leave(self) -> None:
        if self.viewing is not None:
            self.viewing = None
            self.query_one(LogBlocks).display = False
            self.query_one(RunOutput).display = False
            self.query_one(DataTable).display = True
            self.sub_title = ""
            self.refresh_bindings()
            if self.idle:
                self.show_summary()
            else:
                self.show("")
            return
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
