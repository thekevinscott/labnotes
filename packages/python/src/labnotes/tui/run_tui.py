from pathlib import Path

from labnotes.models import LabnotesConfig, Start
from labnotes.tui.config import RUN_COLUMNS
from labnotes.tui.run_app import RunApp


def run_tui(
    start: Start | None,
    title: str,
    config: LabnotesConfig | None = None,
    experiment_config: Path | None = None,
    daemon_request: dict[str, object] | None = None,
    attach: bool = False,
) -> list[dict[str, object]]:
    app = RunApp(
        start,
        title,
        RUN_COLUMNS,
        config=config,
        experiment_config=experiment_config,
        daemon_request=daemon_request,
        attach=attach,
    )
    app.run()
    if app.farewell is not None:
        print(app.farewell)
    if app.error is not None:
        raise app.error
    return app.results
