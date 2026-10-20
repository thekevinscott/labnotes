from urllib.parse import urlencode

from labnotes.models import RunView


def sort_href(view: RunView, column: str) -> str:
    params = [("sort", column)]
    if view.sort == column and not view.descending:
        params.append(("order", "desc"))
    if view.status:
        params.append(("status", view.status))
    params += [(f"f.{name}", value) for name, value in view.filters.items()]
    params += [
        (f"f.{name}", label) for name, picked in view.picked.items() for label in picked
    ]
    return f"?{urlencode(params)}#runs"
