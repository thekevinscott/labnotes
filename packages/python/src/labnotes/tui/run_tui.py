from labnotes.models import Start
from labnotes.tui.run_app import RunApp


def run_tui(start: Start, title: str) -> list[dict[str, object]]:
    app = RunApp(start, title)
    app.run()
    return app.results
