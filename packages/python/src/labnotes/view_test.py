import io
import json
import sys
from unittest import mock

import pytest

from labnotes import view
from labnotes.view import answer, respond, serve

REQUEST = {
    "columns": [{"key": "id", "label": "id"}],
    "rows": {"runs/a": {"id": "a"}, "runs/b": {"id": "b"}},
}


def runs(columns: list[object]) -> tuple[list[object], object]:
    return [*columns, "model"], lambda row: {**row, "model": f"m-{row['id']}"}


def test_is_importable_from_the_package() -> None:
    assert view.serve is serve


def test_answers_with_the_columns_and_a_row_per_run() -> None:
    assert answer(runs, REQUEST) == {
        "columns": [{"key": "id", "label": "id"}, "model"],
        "rows": {
            "runs/a": {"id": "a", "model": "m-a"},
            "runs/b": {"id": "b", "model": "m-b"},
        },
    }


def test_passes_the_native_columns_to_the_function() -> None:
    build = mock.Mock(return_value=([], lambda row: row))

    answer(build, REQUEST)

    build.assert_called_once_with(REQUEST["columns"])


def test_responds_one_line_per_request() -> None:
    out = io.StringIO()

    respond(runs, [json.dumps(REQUEST) + "\n", "\n", json.dumps(REQUEST)], out)

    lines = out.getvalue().splitlines(keepends=True)
    assert [json.loads(line) for line in lines] == [answer(runs, REQUEST)] * 2
    assert all(line.endswith("}\n") for line in lines)


def test_flushes_after_each_response() -> None:
    out = mock.Mock()

    respond(runs, [json.dumps(REQUEST)], out)

    assert out.method_calls == [
        mock.call.write(json.dumps(answer(runs, REQUEST)) + "\n"),
        mock.call.flush(),
    ]


def test_serves_a_function_defined_in_the_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout, stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(REQUEST) + "\n"))
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)

    def noisy(columns: list[object]) -> tuple[list[object], object]:
        print("debugging")
        return runs(columns)

    noisy.__module__ = "__main__"

    assert serve(noisy) is noisy
    assert json.loads(stdout.getvalue()) == answer(runs, REQUEST)
    assert stderr.getvalue() == "debugging\n"
    assert sys.stdout is stdout


def test_leaves_an_imported_function_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    with mock.patch("labnotes.view.respond") as respond:
        assert serve(runs) is runs

    respond.assert_not_called()
