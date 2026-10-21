from labnotes.models import LabnotesConfig
from labnotes.tui.browse_app import BrowseApp


def browse_tui(config: LabnotesConfig, name: str | None) -> None:
    app = BrowseApp(config, name)
    app.run()
    if app.error is not None:
        raise app.error
