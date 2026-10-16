from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.output_html import output_html


@pytest.fixture(autouse=True)
def data_html() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.output_html.data_html", side_effect=lambda data: f"<{data}>"
    ) as patched:
        yield patched


def test_renders_streams_escaped_with_their_name() -> None:
    html = output_html(
        [{"msg_type": "stream", "content": {"name": "stderr", "text": "<oops>\n"}}]
    )

    assert html == '<pre class="stderr">&lt;oops&gt;\n</pre>'


def test_renders_display_data_like_results() -> None:
    html = output_html(
        [{"msg_type": "display_data", "content": {"data": {"text/plain": "shown"}}}]
    )

    assert html == "<{'text/plain': 'shown'}>"


def test_strips_colour_codes_from_tracebacks() -> None:
    html = output_html(
        [
            {
                "msg_type": "error",
                "content": {"traceback": ["\x1b[0;31mZeroDivisionError\x1b[0m", "x"]},
            }
        ]
    )

    assert html == '<pre class="error">ZeroDivisionError\nx</pre>'


def test_skips_other_messages_and_joins_in_order() -> None:
    html = output_html(
        [
            {"msg_type": "status", "content": {}},
            {"msg_type": "stream", "content": {"name": "stdout", "text": "a"}},
            {"msg_type": "execute_result", "content": {"data": {"text/plain": "b"}}},
        ]
    )

    assert html == '<pre class="stdout">a</pre>' + "<{'text/plain': 'b'}>"
