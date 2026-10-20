import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from labnotes.asset_url import asset_url
from labnotes.drain_watch import drain_watch
from labnotes.experiment_notes import experiment_notes
from labnotes.format_duration import format_duration
from labnotes.format_value import format_value
from labnotes.list_experiments import list_experiments
from labnotes.load_experiment import load_experiment
from labnotes.models import LabnotesConfig
from labnotes.notebook_kernel import NotebookKernel
from labnotes.python_blocks import python_blocks
from labnotes.save_note import save_note
from labnotes.saved_outputs import saved_outputs
from labnotes.stop_idle_kernels import stop_idle_kernels
from labnotes.tables.open_tables import open_tables

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.filters["value"] = format_value
templates.env.filters["duration"] = format_duration
templates.env.globals["asset"] = asset_url


def create_app(config: LabnotesConfig, kernel_idle_minutes: float) -> Starlette:
    kernels: dict[tuple[str, str], NotebookKernel] = {}

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        app.state.tables = open_tables(config)
        await app.state.tables.ready()
        watchers = [
            asyncio.create_task(drain_watch(app.state.tables)),
            asyncio.create_task(stop_idle_kernels(kernels, kernel_idle_minutes)),
        ]
        yield
        for watcher in watchers:
            watcher.cancel()
        for kernel in kernels.values():
            await kernel.stop()

    async def index(request: Request) -> Response:
        experiments = await list_experiments(request.app.state.tables, config.mode)
        return templates.TemplateResponse(
            request,
            "index.html",
            {"experiments": experiments, "folder": config.root.name},
        )

    async def experiment(request: Request) -> Response:
        name = request.path_params["name"]
        loaded = await load_experiment(
            request.app.state.tables,
            config.root,
            config.mode,
            name,
            request.query_params,
            lambda note, content: saved_outputs(kernels.get((name, note)), content),
        )
        if loaded is None:
            raise HTTPException(404, "No such experiment")
        return templates.TemplateResponse(
            request, "experiment.html", {"experiment": loaded}
        )

    async def find_note(request: Request) -> dict[str, str]:
        if request.headers.get("content-type") != "application/json":
            raise HTTPException(415, "Send JSON")
        name = request.path_params["name"]
        note = request.path_params["note"]
        found = await experiment_notes(
            request.app.state.tables, config.root, name, note
        )
        if not found:
            raise HTTPException(404, "No such note")
        [note] = found
        return note

    async def put_note(request: Request) -> Response:
        note = await find_note(request)
        body = await request.json()
        base, content = body.get("base"), body.get("content")
        if not isinstance(base, str) or not isinstance(content, str):
            raise HTTPException(400, "Send base and content as strings")
        current = save_note(Path(note["path"]), base, content)
        if current is not None:
            return JSONResponse({"content": current}, status_code=409)
        return Response(status_code=204)

    async def run_block(request: Request) -> Response:
        blocks = python_blocks((await find_note(request))["content"])
        key = (request.path_params["name"], request.path_params["note"])
        block = (await request.json()).get("block")
        if not isinstance(block, int) or not 0 <= block < len(blocks):
            raise HTTPException(400, "No such block")
        if key not in kernels:
            kernels[key] = NotebookKernel(config.root)
        return HTMLResponse(await kernels[key].run(blocks[block]))

    async def restart_kernel(request: Request) -> Response:
        await find_note(request)
        kernel = kernels.get((request.path_params["name"], request.path_params["note"]))
        if kernel is not None:
            await kernel.restart()
        return Response(status_code=204)

    return Starlette(
        routes=[
            Route("/", index),
            Route("/experiments/{name}", experiment),
            Route("/experiments/{name}/notes/{note:path}", put_note, methods=["PUT"]),
            Route(
                "/experiments/{name}/notes/{note:path}/run",
                run_block,
                methods=["POST"],
            ),
            Route(
                "/experiments/{name}/notes/{note:path}/restart",
                restart_kernel,
                methods=["POST"],
            ),
            Mount("/static", StaticFiles(directory=HERE / "static"), name="static"),
        ],
        lifespan=lifespan,
    )
