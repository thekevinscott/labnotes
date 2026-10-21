from labnotes.models import LabnotesConfig
from labnotes.tui.browse_app import BrowseApp


def browse_tui(config: LabnotesConfig, name: str | None) -> None:
    error = BrowseApp(config, name).run()
    if error is not None:
        raise error
