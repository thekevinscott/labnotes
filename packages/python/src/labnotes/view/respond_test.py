import io
import json
from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.view.respond import respond

BUILD = mock.Mock()


@pytest.fixture(autouse=True)
def answer() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.view.respond.answer",
        side_effect=lambda build, request: {"echo": request},
    ) as found:
        yield found


def test_responds_one_line_per_request(answer: mock.MagicMock) -> None:
    out = io.StringIO()

    respond(BUILD, ['{"n": 1}\n', "\n", '{"n": 2}'], out)

    lines = out.getvalue().splitlines(keepends=True)
    assert [json.loads(line) for line in lines] == [
        {"echo": {"n": 1}},
        {"echo": {"n": 2}},
    ]
    assert all(line.endswith("}\n") for line in lines)
    assert answer.call_args_list == [
        mock.call(BUILD, {"n": 1}),
        mock.call(BUILD, {"n": 2}),
    ]


def test_flushes_after_each_response() -> None:
    out = mock.Mock()

    respond(BUILD, ['{"n": 1}'], out)

    assert out.method_calls == [
        mock.call.write(json.dumps({"echo": {"n": 1}}) + "\n"),
        mock.call.flush(),
    ]
