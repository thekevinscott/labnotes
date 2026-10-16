import hashlib
from pathlib import Path
from unittest import mock

from jinja2 import Environment

from labnotes.asset_url import asset_url

STATIC = Path(__file__).parent / "static"


def render(path: str) -> str:
    env = Environment()
    env.globals["asset"] = asset_url
    request = mock.Mock()
    request.url_for = lambda name, /, path: f"/{name}/{path}"
    return env.from_string("{{ asset(path) }}").render(request=request, path=path)


def test_appends_a_digest_of_the_file_contents() -> None:
    digest = hashlib.sha256((STATIC / "labnotes.css").read_bytes()).hexdigest()

    assert render("labnotes.css") == f"/static/labnotes.css?v={digest[:12]}"


def test_each_file_gets_its_own_digest() -> None:
    assert (
        render("row-link.js").split("?v=")[1]
        != (render("view-toggle.js").split("?v=")[1])
    )
