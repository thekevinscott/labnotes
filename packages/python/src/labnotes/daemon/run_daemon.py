import asyncio
import signal

import uvicorn

from labnotes.daemon.daemon_app import daemon_app
from labnotes.daemon.daemon_server import DaemonServer
from labnotes.daemon.exit_when_idle import exit_when_idle
from labnotes.daemon.finalize_lost_runs import finalize_lost_runs
from labnotes.daemon.socket_path import socket_path
from labnotes.models import LabnotesConfig


async def run_daemon(config: LabnotesConfig) -> None:
    await finalize_lost_runs(config)
    path = socket_path(config.root)
    app = daemon_app(config)
    server = DaemonServer(
        uvicorn.Config(app, uds=str(path), lifespan="off", log_level="warning")
    )
    loop = asyncio.get_running_loop()
    for signal_number in (signal.SIGTERM, signal.SIGHUP):
        loop.add_signal_handler(signal_number, app.state.stop)
    watcher = asyncio.create_task(exit_when_idle(server, app.state.idle))
    try:
        await server.serve()
    finally:
        watcher.cancel()
        path.unlink(missing_ok=True)
