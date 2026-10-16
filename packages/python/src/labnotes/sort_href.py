from urllib.parse import urlencode

from labnotes.models import RunView


def sort_href(view: RunView, column: str) -> str:
    params = {"sort": column}
    if view.sort == column and not view.descending:
        params["order"] = "desc"
    if view.status:
        params["status"] = view.status
    params.update({f"f.{name}": value for name, value in view.filters.items()})
    return f"?{urlencode(params)}#runs"
