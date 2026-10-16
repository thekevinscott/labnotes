import hashlib
from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.asset_url import _digest, asset_url


@pytest.fixture
def static() -> Iterator[mock.MagicMock]:
    _digest.cache_clear()
    with mock.patch("labnotes.asset_url.STATIC") as folder:
        folder.__truediv__.side_effect = lambda path: mock.Mock(
            read_bytes=mock.Mock(return_value=path.encode())
        )
        yield folder
    _digest.cache_clear()


def url(path: str) -> str:
    request = mock.Mock()
    request.url_for = lambda name, /, path: f"/{name}/{path}"
    return asset_url({"request": request}, path)


def test_appends_a_digest_of_the_file_contents(static: mock.MagicMock) -> None:
    digest = hashlib.sha256(b"labnotes.css").hexdigest()[:12]

    assert url("labnotes.css") == f"/static/labnotes.css?v={digest}"
    static.__truediv__.assert_called_once_with("labnotes.css")


def test_each_file_gets_its_own_digest(static: mock.MagicMock) -> None:
    assert url("a.js").split("?v=")[1] != url("b.js").split("?v=")[1]


def test_reads_each_file_once(static: mock.MagicMock) -> None:
    url("a.js")
    url("a.js")

    static.__truediv__.assert_called_once_with("a.js")


def test_jinja_hands_it_the_template_context() -> None:
    assert getattr(asset_url, "jinja_pass_arg").name == "context"
