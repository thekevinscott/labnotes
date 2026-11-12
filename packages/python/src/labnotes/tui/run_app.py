import asyncio
import contextlib
import json
import signal
import socket
import time
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from rich.text import Text
from starlette.datastructures import QueryParams
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import ContentSwitcher, DataTable, Footer, Header, Input, Static

from labnotes.compose_experiment import compose_experiment
from labnotes.daemon.command import command as daemon_command
from labnotes.daemon.client import daemon_socket
from labnotes.daemon.request_start import request_start
from labnotes.daemon.ensure import ensure_daemon
from labnotes.load_experiment import load_experiment
from labnotes.models import Controls, LabnotesConfig, Start
from labnotes.retries import RETRY_EXIT_CODE
from labnotes.runner.describe_event import describe_event
from labnotes.runner.param_args import param_args
from labnotes.runner.stop_then_kill import GRACE_SECONDS, stop_then_kill
from labnotes.tables.open_tables import open_tables
from labnotes.tui.config import RUN_COLUMNS
from labnotes.tui.count_runs import count_runs
from labnotes.tui.dim import dim
from labnotes.tui.flash_value import FlashValue
from labnotes.tui.format_elapsed import format_elapsed
from labnotes.tui.hook_panel import HookPanel
from labnotes.tui.leave_prompt import (
    DetachedLeavePrompt,
    LeavePrompt,
    LostDaemonNotice,
)
from labnotes.tui.log_blocks import LogBlocks
from labnotes.tui.native_rows import native_rows
from labnotes.tui.reload_on_change import reload_on_change
from labnotes.tui.restart_request import restart_request
from labnotes.tui.run_output import RunOutput
from labnotes.tui.runs_table import RunsTable
from labnotes.tui.stage_line import stage_line
from labnotes.tui.startup_steps import startup_steps
from labnotes.tui.view_pane import ViewPane
from labnotes.tui.view_switcher import ViewSwitcher
from labnotes.utils.format_bytes import format_bytes
from labnotes.utils.run_usage import run_usage
from labnotes.view.experiment import Experiment
from labnotes.view_specs import view_specs
from labnotes.watch_rows import watch_rows

PENDING, PASSED, FAILED = "○", "✓", "✗"
SPINNER = "|/-\\"
SKIPPED = "–"
STAGES = ("setup", "runs", "teardown")
HOOKS = ("setup", "teardown")
VIEWING_ACTIONS = {"leave", "quit", "interrupt", "command_palette", "finish_up"}
RUNS_ACTIONS = {"kill_run", "restart_run", "filter", "leave"}
BUILT_IN = "labnotes.tui.run_app:RunLiveView"


class RunLiveView(Widget):
    DEFAULT_CSS = """
    RunLiveView { height: 1fr; }
    RunLiveView #runs-stage { height: 1fr; }
    RunLiveView RunsTable { height: 1fr; }
    RunLiveView #stages { padding: 0 1; display: none; }
    """
    BINDINGS = [
        Binding("f", "finish_up", "Finish up"),
        Binding("x", "kill_run", "Stop run"),
        Binding("r", "restart_run", "Restart"),
        Binding("slash", "filter", "Filter", key_display="/"),
        Binding("escape", "leave", "Back"),
        Binding("plus,equals_sign", "concurrency(1)", "More at once", key_display="+"),
        Binding("minus", "concurrency(-1)", "Fewer at once", key_display="-"),
        Binding("left_square_bracket", "stage(-1)", "Previous stage", show=False),
        Binding("right_square_bracket", "stage(1)", "Next stage", show=False),
    ]

    def __init__(self, columns: Sequence[str] = ()) -> None:
        super().__init__()
        self.columns = tuple(columns or RUN_COLUMNS)
        self.controls = Controls(
            lambda: None,
            lambda count: None,
            lambda run: None,
            lambda: None,
            lambda: None,
        )
        self.concurrency = 1
        self.idle = False
        self.ended: set[str] = set()
        self.frame = 0
        self.started: dict[str, float] = {}
        self.pending: set[str] = set()
        self.cells: dict[str, dict[str, object]] = {}
        self.filter = ""
        self.failed: set[str] = set()
        self.retried: set[str] = set()
        self.waiting: dict[str, float] = {}
        self.folders: dict[str, Path] = {}
        self.viewing: str | None = None
        self.sampling = False
        self.unmeasured: dict[str, None] = {}
        self.hooks: tuple[str, ...] = ()
        self.stage = "runs"
        self.moved = False
        self.notice = ""

    def compose(self) -> ComposeResult:
        yield Static(id="stages")
        yield HookPanel("setup", id="setup-stage")
        with Vertical(id="runs-stage"):
            yield RunsTable(id="runs", cursor_type="row")
            yield LogBlocks(id="blocks")
            yield RunOutput(id="output")
            yield Input(id="filter", placeholder="Filter params")
        yield HookPanel("teardown", id="teardown-stage")
        yield Static(id="status")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        for column in self.columns:
            table.add_column(column, key=column)
        self.query_one(Input).display = False
        self.query_one("#output", RunOutput).display = False
        table.focus()
        self.set_interval(0.1, self.spin)
        self.set_interval(1, self.tick)
        self.set_interval(0.25, self.follow)

    def show_event(self, event: dict[str, object]) -> None:
        table = self.query_one(DataTable)
        run = str(event.get("run"))
        match event["event"]:
            case "planned":
                self.app.title = str(event["title"])
                first = not self.cells
                for planned in event["runs"]:  # type: ignore[attr-defined]
                    args = " ".join(param_args(planned["params"]))
                    self.cells[planned["run"]] = self.waiting_cells(
                        planned["run"], args
                    )
                    self.pending.add(planned["run"])
                self.redraw(table.cursor_row)
                self.show_concurrency(event)
                self.hooks = tuple(cast(list[str], event.get("hooks", [])))
                if self.hooks:
                    self.query_one("#stages").display = True
                    self.go(self.stage_names()[0])
                match event["runs"]:
                    case [only] if first:
                        self.view(only["run"])  # type: ignore[index]
            case "started":
                self.idle = False
                self.pending.discard(run)
                self.started[run] = self.since(event)
                self.folders[run] = Path(str(event["folder"]))
                args = " ".join(param_args(event["params"]))  # type: ignore[arg-type]
                shown = {
                    "run": run,
                    "params": args,
                    "status": SPINNER[self.frame],
                    "time": format_elapsed(0),
                }
                for column, cell in shown.items():
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
                self.unmeasured[run] = None
                self.measure()
            case "retrying":
                self.waiting[run] = time.monotonic() + (
                    max(0.0, float(str(event["retry_at"])) - time.time())
                    if "retry_at" in event
                    else float(str(event["seconds"]))
                )
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
                again = str(event["retry"])
                if again == run:
                    self.failed.discard(run)
                    self.ended.discard(run)
                else:
                    self.retried.add(run)
                args = " ".join(param_args(event["params"]))  # type: ignore[arg-type]
                self.cells[again] = self.waiting_cells(again, args)
                self.pending.add(again)
                self.redraw(table.cursor_row)
                self.show(describe_event(event))
            case "setting up" | "tearing down" if "folder" in event:
                panel = self.panel(str(event["hook"]))
                panel.start(Path(str(event["folder"])), self.since(event))
                self.advance(panel.hook)
                self.show(describe_event(event))
            case "hook ended":
                panel = self.panel(str(event["hook"]))
                error = event["error"]
                panel.end(None if error is None else str(error), self.since(event))
                match panel.hook, panel.state:
                    case "setup", "passed":
                        self.advance("runs")
                self.draw_stages()
                if self.idle and error is None:
                    self.show_summary()
                else:
                    self.show(describe_event(event))
            case "idle":
                self.idle = True
                self.draw_stages()
                self.show_summary()
            case "concurrency":
                self.show_concurrency(event)
            case "stopping" | "finishing up":
                for pending in self.pending:
                    self.set_cell(pending, "status", dim(SKIPPED))
                self.notice = describe_event(event)
                self.show(self.notice)
            case _:
                self.show(describe_event(event))

    def since(self, event: dict[str, object]) -> float:
        if "at" not in event:
            return time.monotonic()
        return time.monotonic() - max(0.0, time.time() - float(str(event["at"])))

    def panel(self, hook: str) -> HookPanel:
        return self.query_one(f"#{hook}-stage", HookPanel)

    def stage_names(self) -> list[str]:
        shown = {"runs", *self.hooks}
        return [name for name in STAGES if name in shown]

    def stage_state(self, stage: str) -> str:
        if stage in HOOKS:
            return self.panel(stage).state
        if self.idle:
            return "failed" if self.failed - self.retried else "passed"
        return "running" if self.started or self.ended else "waiting"

    def draw_stages(self) -> None:
        if self.hooks:
            stages = [(name, self.stage_state(name)) for name in self.stage_names()]
            line = stage_line(stages, self.stage, SPINNER[self.frame])
            self.query_one("#stages", Static).update(line)

    def go(self, stage: str) -> None:
        self.stage = stage
        for name in STAGES:
            self.query_one(f"#{name}-stage").display = name == stage
        if stage in HOOKS:
            self.panel(stage).query_one(RunOutput).focus()
        elif self.viewing is None:
            self.query_one(DataTable).focus()
        else:
            self.query_one("#output", RunOutput).focus()
        self.draw_stages()
        self.refresh_bindings()

    def advance(self, stage: str) -> None:
        if not self.moved and stage in self.stage_names():
            self.go(stage)

    def action_stage(self, step: int) -> None:
        names = self.stage_names()
        index = min(max(names.index(self.stage) + step, 0), len(names) - 1)
        self.moved = True
        self.go(names[index])

    def on_click(self, event: events.Click) -> None:
        picked = event.style.meta.get("stage")
        if picked in self.stage_names():
            self.moved = True
            self.go(picked)

    def busy(self) -> str | None:
        torn = "teardown" in self.hooks
        match self.panel("setup").state, self.panel("teardown").state:
            case _, "passed" | "failed" if torn:
                return None
            case "failed", _ if not torn:
                return None
            case _ if self.idle and not torn:
                return None
            case "running", _:
                return "Setting up."
            case ("failed", _) | (_, "running"):
                return "Tearing down."
        if self.idle:
            return "Tearing down."
        if self.started:
            return f"{count_runs(len(self.started))} still going."
        if self.waiting:
            return f"{count_runs(len(self.waiting))} waiting to retry."
        return "Starting runs."

    def show_summary(self) -> None:
        retried = len(self.retried)
        failed = len(self.failed - self.retried)
        passed = len(self.ended) - failed - retried
        again = f" {retried} retried." if retried else ""
        self.show(f"{passed} passed, {failed} failed.{again} Ctrl-C to quit.")

    def redraw(self, row: int) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for run, cells in self.cells.items():
            if self.filter in str(cells.get("params", "")):
                table.add_row(
                    *(cells.get(c, "") for c in self.columns),
                    key=run,
                    label=str(table.row_count + 1),
                )
        table.move_cursor(row=row)

    def waiting_cells(self, run: str, args: str) -> dict[str, object]:
        shown = {"run": run, "params": args, "status": PENDING}
        return {
            column: dim(shown.get(column, "")) for column in {*self.columns, *shown}
        }

    def set_cell(self, run: str, column: str, cell: object) -> None:
        self.cells[run][column] = cell
        table = self.query_one(DataTable)
        if run in table.rows and column in self.columns:
            table.update_cell(run, column, cell, update_width=True)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        if isinstance(self.app.screen, LeavePrompt):
            return False
        match action:
            case "stage":
                return bool(self.hooks)
            case _ if self.stage in HOOKS and action in RUNS_ACTIONS:
                return False
            case "leave" if self.viewing is None:
                return self.query_one(Input).display
        return self.viewing is None or action in VIEWING_ACTIONS

    def show_concurrency(self, event: dict[str, object]) -> None:
        self.concurrency = int(event["concurrency"])  # type: ignore[call-overload]
        at = event.get("at")
        self.app.query_one("#concurrency", FlashValue).set_value(
            f"{self.concurrency} at a time", None if at is None else float(str(at))
        )

    def tick(self) -> None:
        now = time.monotonic()
        for run, began in self.started.items():
            self.set_cell(run, "time", format_elapsed(now - began))
        for run, due in self.waiting.items():
            wait = format_elapsed(max(0, due - now))
            outcome = f"{FAILED} exited {RETRY_EXIT_CODE}, retry in {wait}"
            self.set_cell(run, "status", Text(outcome, style="yellow"))
        if self.started:
            self.measure()
        for panel in self.query(HookPanel):
            if panel.running:
                panel.tick()

    def measure(self) -> None:
        if not self.sampling:
            self.sampling = True
            self.sample()

    @work
    async def sample(self) -> None:
        try:
            for run in list(self.started):
                usage = await run_usage(self.folders[run], True)
                if run in self.started:
                    self.show_usage(run, usage)
            while self.unmeasured:
                run = next(iter(self.unmeasured))
                del self.unmeasured[run]
                self.show_usage(run, await run_usage(self.folders[run], False))
        finally:
            self.sampling = False

    def show_usage(self, run: str, usage: dict[str, int | None]) -> None:
        self.set_cell(run, "memory", format_bytes(usage["memory"]))
        self.set_cell(run, "size", format_bytes(usage["size"]))

    def spin(self) -> None:
        self.frame = (self.frame + 1) % len(SPINNER)
        for run in self.started:
            self.set_cell(run, "status", SPINNER[self.frame])
        self.draw_stages()

    def show(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def cursor_run(self) -> str | None:
        table = self.query_one(DataTable)
        if not table.row_count:
            return None
        cell = table.coordinate_to_cell_key(table.cursor_coordinate)
        return str(cell.row_key.value)

    def action_kill_run(self) -> None:
        if (run := self.cursor_run()) is not None:
            self.controls.kill(run)

    def action_finish_up(self) -> None:
        self.controls.finish_up()

    def action_concurrency(self, change: int) -> None:
        self.controls.set_concurrency(self.concurrency + change)

    def action_restart_run(self) -> None:
        if (run := self.cursor_run()) is not None and isinstance(self.app, RunApp):
            self.app.restart_run(run)

    def action_filter(self) -> None:
        field = self.query_one(Input)
        field.display = True
        field.focus()
        self.refresh_bindings()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.view(str(event.row_key.value))

    def view(self, run: str) -> None:
        self.viewing = run
        self.query_one(LogBlocks).reset()
        self.query_one("#output", RunOutput).reset()
        self.query_one(DataTable).display = False
        self.query_one("#output", RunOutput).display = True
        self.query_one("#output", RunOutput).focus()
        self.app.sub_title = run
        self.show("")
        self.refresh_bindings()
        self.follow()

    def follow(self) -> None:
        for panel in self.query(HookPanel):
            if panel.running:
                panel.follow()
        if self.viewing in self.folders:
            self.query_one(LogBlocks).follow(self.folders[self.viewing])
            self.query_one("#output", RunOutput).follow(self.folders[self.viewing])

    def action_leave(self) -> None:
        if self.viewing is not None:
            self.viewing = None
            self.query_one(LogBlocks).display = False
            self.query_one("#output", RunOutput).display = False
            self.query_one(DataTable).display = True
            self.query_one(DataTable).focus()
            self.app.sub_title = ""
            self.refresh_bindings()
            if self.idle:
                self.show_summary()
            else:
                self.show(self.notice)
            return
        field = self.query_one(Input)
        field.value = ""
        field.display = False
        self.query_one(DataTable).focus()
        self.refresh_bindings()

    def on_input_changed(self, event: Input.Changed) -> None:
        self.filter = event.value
        self.redraw(self.query_one(DataTable).cursor_row)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.input.display = bool(event.value)
        self.query_one(DataTable).focus()
        self.refresh_bindings()


class RunApp(ViewSwitcher, App[None]):
    CSS = """
    #concurrency { dock: right; width: auto; padding: 0 1; }
    #startup { height: 1fr; padding: 1 2; display: none; }
    """
    BINDINGS = [Binding("ctrl+c", "interrupt", "Quit")]

    def __init__(
        self,
        start: Start | None,
        title: str,
        columns: Sequence[str],
        config: LabnotesConfig | None = None,
        experiment_config: Path | None = None,
        daemon_batch: str | None = None,
        daemon_request: dict[str, object] | None = None,
        attach: bool = False,
    ) -> None:
        super().__init__()
        self.start = start
        self.title = title
        self.config = config
        self.experiment_config = experiment_config
        self.experiment_name = title
        self.view_specs = self.configured_views()
        self.results: list[dict[str, object]] = []
        self.error: Exception | None = None
        self.columns = tuple(columns)
        self.body = RunLiveView(columns)
        self.body.id = "view-1"
        self.body_ready = True
        self.loaded_views = False
        self.shown: Experiment | None = None
        self.left: dict[str, Widget] = {}
        self.controls = self.body.controls
        self.daemon_batch = daemon_batch
        self.daemon_request = daemon_request
        self.steps: list[str] = []
        self.startup_frame = 0
        self.attach = attach
        self.busy_batches: set[str] = set()
        self.restart_batches: set[str] = set()
        self.disconnected = False
        self.attached: socket.socket | None = None
        self.leaving = False
        self.farewell: str | None = None
        self.finishing_up = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="startup")
        with ContentSwitcher(initial="view-1"):
            if self.view_specs:
                assert self.config is not None
                yield ViewPane("runs", BUILT_IN, self.config.root, id="view-1")
            else:
                yield self.body
        yield Footer()

    async def on_mount(self) -> None:
        await self.query_one(Header).mount(FlashValue(id="concurrency"))
        if self.view_specs:
            assert self.config is not None
            self._bindings.bind("escape", "leave", "Back")
            try:
                self.body = self.query_one(RunLiveView)
            except NoMatches:
                # ViewPane already displays the built-in view's loading error.
                self.body_ready = False
            tables = open_tables(self.config, run_files=True)
            self.run_worker(
                reload_on_change(
                    watch_rows(
                        tables, {"runs", "experiment_configs"}, self.experiment_name
                    ),
                    lambda: self.load_data(tables),
                    lambda error: None,
                ),
                exit_on_error=False,
            )
            self.run_worker(self.watch_files(tables), exit_on_error=False)
        if self.daemon_request is not None:
            self.query_one("#startup").display = True
            self.query_one(ContentSwitcher).display = False
            self.startup_timer = self.set_interval(0.1, self.spin_startup)  # probe
            self.run_worker(self.start_daemon_run())
        elif self.daemon_batch is not None or self.attach:
            try:
                self.follow_daemon()
            except (OSError, ValueError) as error:
                self.error = error
                self.exit()
        else:
            self.run_worker(self.drive())

    def step(self, step: str) -> None:
        if self.steps[-1:] != [step]:
            self.steps.append(step)
        self.spin_startup()

    def spin_startup(self) -> None:
        self.startup_frame = (self.startup_frame + 1) % len(SPINNER)
        self.query_one("#startup", Static).update(
            startup_steps(self.steps, SPINNER[self.startup_frame])
        )

    async def start_daemon_run(self) -> None:
        assert self.config is not None
        assert self.daemon_request is not None
        try:
            self.step("Starting up")
            await ensure_daemon(self.config, self.experiment_name)
            self.attach_daemon()
            reply = await request_start(
                self.config, self.experiment_name, self.daemon_request, self.step
            )
            self.daemon_batch = str(reply["batch"])
            self.follow_daemon()
        except (OSError, ValueError) as error:
            self.error = ValueError(str(error))
            self.exit()
            return
        self.startup_timer.stop()
        self.query_one("#startup").display = False
        self.query_one(ContentSwitcher).display = True
        # Focus requests made while the views were hidden were dropped.
        if self.body_ready:
            self.call_after_refresh(lambda: self.body.go(self.body.stage))
        else:
            self.call_after_refresh(self.screen.focus_next)

    def follow_daemon(self) -> None:
        batches = self.attach_daemon() if self.attached is None else []
        if self.attach:
            if not batches:
                self.farewell = f"Nothing is running for {self.experiment_name}."
                self.exit()
                return
            self.daemon_batch = batches[0]
        assert self.daemon_batch is not None
        batch = self.daemon_batch
        self.listen(
            Controls(
                lambda: self.queue_command({"command": "stop_all"}),
                lambda count: self.queue_command(
                    {
                        "command": "set_concurrency",
                        "count": count,
                        "batch": None if self.attach else batch,
                    }
                ),
                lambda run: self.queue_command({"command": "stop_one", "run": run}),
                lambda: None,
                lambda: self.queue_command({"command": "finish_up"}),
            )
        )
        self.run_worker(self.read_stream())

    def attach_daemon(self) -> list[str]:
        assert self.config is not None
        path = daemon_socket(self.config, self.experiment_name)
        if path is None:
            raise ValueError(f"No daemon is running for {self.experiment_name}.")
        client = socket.socket(socket.AF_UNIX)
        try:
            client.settimeout(10)
            client.connect(str(path))
            client.sendall(b'{"command":"attach"}\n')
            with socket.SocketIO(client, "rb") as replies:
                reply = json.loads(replies.readline())
            if not reply.get("ok"):
                raise ValueError(str(reply.get("error", "Daemon rejected attach")))
        except Exception:
            client.close()
            raise
        self.attached = client
        return cast(list[str], reply.get("batches", []))

    async def read_stream(self) -> None:
        if self.attached is None:
            return
        writer = None
        try:
            reader, writer = await asyncio.open_connection(
                sock=self.attached, limit=16 * 1024 * 1024
            )
            while line := await reader.readline():
                message = json.loads(line)
                if self.body_ready:
                    self.forward(str(message["batch"]), message["event"])
        except (OSError, ValueError):
            pass  # Keep the last visible state when the stream is lost.
        finally:
            if writer is not None:
                writer.close()
            self.disconnected = True
            with contextlib.suppress(NoMatches):
                self.query_one("#concurrency", FlashValue).update(
                    f"{self.body.concurrency} at a time · disconnected"
                )
        if self.leaving:
            return
        notice = (
            f"Lost the daemon for {self.experiment_name}. "
            "This view is no longer live."
        )
        self.error = ValueError(notice)
        self.push_screen(LostDaemonNotice(notice), lambda _: self.exit())

    def on_unmount(self) -> None:
        self.leaving = True
        if self.attached is not None:
            self.attached.close()

    def queue_command(self, message: dict[str, object]) -> None:
        self.run_worker(self.send_command(message), exit_on_error=False)

    async def send_command(self, message: dict[str, object]) -> None:
        assert self.config is not None
        if self.disconnected:
            self.body.show("disconnected")
            return
        try:
            reply = await asyncio.to_thread(
                daemon_command, self.config, self.experiment_name, message
            )
            if not reply.get("ok"):
                raise ValueError(str(reply.get("error", "Daemon rejected command")))
        except (OSError, ValueError) as error:
            if self.body_ready:
                self.body.show(str(error))

    def restart_run(self, run: str) -> None:
        if self.daemon_batch is None:
            return
        if run not in self.body.failed:
            self.body.show(f"{run} has not failed.")
            return
        self.run_worker(self.restart_daemon_run(run), exit_on_error=False)

    async def restart_daemon_run(self, run: str) -> None:
        assert self.config is not None
        if self.disconnected:
            self.body.show("disconnected")
            return
        try:
            await request_start(
                self.config,
                self.experiment_name,
                restart_request(run, self.experiment_config),
                lambda step: self.body.show(f"Restarting {run}: {step}"),
            )
            self.body.show(f"Restarted {run}.")
        except (OSError, ValueError) as error:
            self.body.show(f"Could not restart {run}: {error}")

    def configured_views(self) -> dict[str, str]:
        if self.config is None:
            return {}
        folder = self.config.experiments.replace("{experiment}", self.experiment_name)
        path = self.experiment_config or self.config.root / folder / "experiment.toml"
        try:
            source = path.read_text()
            layer = tomllib.loads(source)
        except (OSError, tomllib.TOMLDecodeError):
            # The runner reports missing or invalid config through its normal path.
            layer = {}
        return view_specs(compose_experiment(self.config.defaults, layer))

    async def load_data(self, tables: Any) -> None:
        assert self.config is not None
        loaded = await load_experiment(
            tables, self.config.root, self.experiment_name, QueryParams()
        )
        if loaded is None:
            return
        if not self.loaded_views:
            await self.add_views(
                cast(Mapping[str, str], loaded["views"]), self.config.root
            )
            self.loaded_views = True
        self.shown = Experiment(
            self.config.root,
            self.experiment_name,
            native_rows(loaded),
            MappingProxyType(cast(dict[str, Any], loaded["config"] or {})),
        )
        self.deliver(self.shown)

    async def watch_files(self, tables: Any) -> None:
        async for row in watch_rows(tables, {"run_files"}, self.experiment_name):
            if self.shown is not None:
                self.deliver(self.shown, frozenset({str(row["path"])}))

    async def drive(self) -> None:
        assert self.start is not None
        try:
            self.results = await self.start(self.show_event, self.listen)
        except Exception as error:
            self.error = error
        if not self.finishing_up or self.error is not None:
            self.exit()

    def listen(self, controls: Controls) -> None:
        self.controls = controls
        if self.body_ready:
            self.body.controls = controls
        if self.daemon_batch is None:
            stop_then_kill(self.stop_runs, signal.SIGTERM)
            stop_then_kill(self.stop_runs, signal.SIGHUP)

    def show_event(self, event: dict[str, object]) -> None:
        if event["event"] == "finishing up":
            self.finishing_up = True
        if self.body_ready:
            self.body.show_event(event)

    def forward(self, batch: str, event: dict[str, object]) -> None:
        if (
            not self.attach
            and self.daemon_batch is not None
            and batch != self.daemon_batch
            and batch not in self.restart_batches
        ):
            match event:
                case {
                    "event": "planned",
                    "restart": str(run),
                } if run in self.body.cells:
                    self.restart_batches.add(batch)
                case _:
                    return
        match event:
            case {"event": "planned", "restart": str(run)} if run in self.body.cells:
                [planned] = cast(list[dict[str, object]], event["runs"])
                event = {
                    "event": "retried",
                    "run": run,
                    "retry": planned["run"],
                    "params": planned["params"],
                }
            case {"event": "started"}:
                self.busy_batches.add(batch)
            case {"event": "idle"}:
                self.busy_batches.discard(batch)
                if self.busy_batches:
                    return
        self.body.show_event(event)

    def stop_runs(self) -> None:
        if self.body_ready and self.body.idle:
            if self.finishing_up:
                self.exit()
            else:
                self.controls.finish()
        else:
            self.controls.interrupt()

    def action_interrupt(self) -> None:
        if self.daemon_request is not None and self.daemon_batch is None:
            name = self.experiment_name
            self.farewell = f"{name} may still start. Stop it with: labnotes experiments {name} stop"
            self.exit()
            return
        if self.daemon_batch is not None:
            busy = self.body.busy() if self.body_ready else "Still running."
            if busy is None:
                self.exit()
            else:
                self.push_screen(DetachedLeavePrompt(busy), self.answer)
            return
        if self.body_ready and self.body.started:
            self.push_screen(LeavePrompt(len(self.body.started)), self.answer)
        elif self.body_ready and self.body.idle:
            if self.finishing_up:
                self.exit()
            else:
                self.controls.finish()
        else:
            self.exit()

    async def action_quit(self) -> None:
        self.action_interrupt()

    def answer(self, choice: str | None) -> None:
        if choice == "stop":
            if self.daemon_batch is None:
                self.controls.interrupt()
                self.set_timer(GRACE_SECONDS, self.controls.interrupt)
            else:
                self.run_worker(self.stop_daemon_and_exit(), exit_on_error=False)
        elif choice == "leave" and self.daemon_batch is not None:
            name = self.experiment_name
            self.farewell = (
                f"{name} is still running.\n"
                f"Reattach with: labnotes experiments {name} attach\n"
                f"Stop it with: labnotes experiments {name} stop"
            )
            self.exit()

    async def stop_daemon_and_exit(self) -> None:
        self.leaving = True
        await self.send_command({"command": "stop_all"})
        self.exit()

    def action_leave(self) -> None:
        match self.query_one(ContentSwitcher).current:
            case "view-1":
                pass
            case _:
                self.action_show_view(1)
