import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from labnotes.drain_watch import drain_watch
from labnotes.format_value import format_value
from labnotes.list_experiments import list_experiments
from labnotes.load_experiment import load_experiment
from labnotes.open_experiments import open_experiments
from labnotes.open_runs import open_runs
from labnotes.pivot_cells import pivot_cells

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.filters["value"] = format_value


def create_app(experiments_folder: Path, data_folder: Path) -> Starlette:
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
        loaded = await load_experiment(
            state.experiments, state.runs, request.path_params["name"]
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

    return Starlette(
        routes=[
            Route("/", index),
            Route("/experiments/{name}", experiment),
            Mount("/static", StaticFiles(directory=HERE / "static"), name="static"),
        ],
        lifespan=lifespan,
    )
