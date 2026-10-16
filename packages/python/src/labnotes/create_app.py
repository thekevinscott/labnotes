import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from labnotes.asset_url import asset_url
from labnotes.drain_watch import drain_watch
from labnotes.format_value import format_value
from labnotes.list_experiments import list_experiments
from labnotes.load_experiment import load_experiment
from labnotes.notebook_kernel import NotebookKernel
from labnotes.open_experiments import open_experiments
from labnotes.open_runs import open_runs
from labnotes.pivot_cells import pivot_cells
from labnotes.python_blocks import python_blocks
from labnotes.saved_outputs import saved_outputs
from labnotes.sql_quote import quote_string

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.filters["value"] = format_value
templates.env.globals["asset"] = asset_url


def create_app(experiments_folder: Path, data_folder: Path) -> Starlette:
    kernels: dict[tuple[str, str], NotebookKernel] = {}

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        app.state.experiments = open_experiments(experiments_folder)
        app.state.runs = open_runs(data_folder)
        await app.state.experiments.ready()
        await app.state.runs.ready()
        watchers = [
            asyncio.create_task(drain_watch(app.state.experiments)),
            asyncio.create_task(drain_watch(app.state.runs)),
        ]
        yield
        for watcher in watchers:
            watcher.cancel()
        for kernel in kernels.values():
            await kernel.stop()

    async def index(request: Request) -> Response:
        state = request.app.state
        experiments = await list_experiments(state.experiments, state.runs)
        return templates.TemplateResponse(
            request,
            "index.html",
            {"experiments": experiments, "folder": experiments_folder.resolve().name},
        )

    async def experiment(request: Request) -> Response:
        state = request.app.state
        name = request.path_params["name"]
        loaded = await load_experiment(
            state.experiments,
            state.runs,
            name,
            request.query_params,
            lambda note, content: saved_outputs(kernels.get((name, note)), content),
        )
        if loaded is None:
            raise HTTPException(404, "No such experiment")
        varies = cast(dict[str, list[object]], loaded["varies"])
        cells = cast(list[dict[str, object]], loaded["cells"])
        return templates.TemplateResponse(
            request,
            "experiment.html",
            {"experiment": loaded, "pivot": pivot_cells(varies, cells)},
        )

    async def run_block(request: Request) -> Response:
        if request.headers.get("content-type") != "application/json":
            raise HTTPException(415, "Send JSON")
        name = request.path_params["name"]
        note = request.path_params["note"]
        found = await request.app.state.experiments.query(
            "SELECT content FROM notes"
            f" WHERE experiment = {quote_string(name)} AND name = {quote_string(note)}"
        )
        if not found:
            raise HTTPException(404, "No such note")
        blocks = python_blocks(str(found[0]["content"]))
        block = (await request.json()).get("block")
        if not isinstance(block, int) or not 0 <= block < len(blocks):
            raise HTTPException(400, "No such block")
        if (name, note) not in kernels:
            kernels[(name, note)] = NotebookKernel(data_folder)
        return HTMLResponse(await kernels[(name, note)].run(blocks[block]))

    return Starlette(
        routes=[
            Route("/", index),
            Route("/experiments/{name}", experiment),
            Route("/experiments/{name}/notes/{note}/run", run_block, methods=["POST"]),
            Mount("/static", StaticFiles(directory=HERE / "static"), name="static"),
        ],
        lifespan=lifespan,
    )
