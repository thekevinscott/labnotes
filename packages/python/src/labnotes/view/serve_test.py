import io
import sys
from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest

from labnotes.view.serve import serve


def runs(columns: list[Any]) -> tuple[list[Any], Any]:
    return columns, lambda row: row


@pytest.fixture
def respond() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.view.serve.respond") as found:
        yield found


def test_serves_a_function_defined_in_the_script(
    monkeypatch: pytest.MonkeyPatch, respond: mock.MagicMock
) -> None:
    stdin, stdout, stderr = io.StringIO(), io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    respond.side_effect = lambda build, lines, out: print("debugging")

    def script(columns: list[Any]) -> tuple[list[Any], Any]:
        return runs(columns)

    script.__module__ = "__main__"

    assert serve(script) is script
    respond.assert_called_once_with(script, stdin, stdout)
    assert stderr.getvalue() == "debugging\n"
    assert stdout.getvalue() == ""
    assert sys.stdout is stdout


def test_restores_stdout_when_serving_fails(
    monkeypatch: pytest.MonkeyPatch, respond: mock.MagicMock
) -> None:
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)
    respond.side_effect = ValueError("bad request")

    def script(columns: list[Any]) -> tuple[list[Any], Any]:
        return runs(columns)

    script.__module__ = "__main__"

    with pytest.raises(ValueError, match="bad request"):
        serve(script)
    assert sys.stdout is stdout


def test_leaves_an_imported_function_alone(respond: mock.MagicMock) -> None:
    assert serve(runs) is runs

    respond.assert_not_called()


def test_serves_whatever_string_names_the_script(
    monkeypatch: pytest.MonkeyPatch, respond: mock.MagicMock
) -> None:
    monkeypatch.setattr(sys, "stdout", io.StringIO())

    def script(columns: list[Any]) -> tuple[list[Any], Any]:
        return runs(columns)

    script.__module__ = "".join(["__ma", "in__"])

    serve(script)

    respond.assert_called_once()


def test_leaves_a_module_that_sorts_before_main_alone(
    respond: mock.MagicMock,
) -> None:
    def script(columns: list[Any]) -> tuple[list[Any], Any]:
        return runs(columns)

    script.__module__ = "Views"

    assert serve(script) is script
    respond.assert_not_called()
