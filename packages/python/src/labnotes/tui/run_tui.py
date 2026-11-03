from labnotes.models import LabnotesConfig, Start
from labnotes.tui.config import RUN_COLUMNS
from labnotes.tui.run_app import RunApp


def run_tui(
    start: Start, title: str, config: LabnotesConfig | None = None
) -> list[dict[str, object]]:
    app = RunApp(start, title, RUN_COLUMNS, config=config)
    app.run()
    if app.error is not None:
        raise app.error
    return app.results
