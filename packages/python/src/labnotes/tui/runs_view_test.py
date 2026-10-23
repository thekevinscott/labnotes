import asyncio
import json
from typing import Any
from unittest import mock

import pytest

from labnotes.tui.runs_view import RunsView

COLUMNS = [{"key": "id", "label": "id"}]
A = {"id": "a", "folder": "runs/a"}
B = {"id": "b", "folder": "runs/b"}


def view(*replies: object, elapsed: float = 0.01) -> RunsView:
    answers = [
        reply if isinstance(reply, BaseException) else (json.dumps(reply), elapsed)
        for reply in replies
    ]
    return RunsView(mock.AsyncMock(side_effect=answers))


def answer(request: dict[str, Any], **extra: object) -> dict[str, Any]:
    return {
        "columns": [*request["columns"], *extra],
        "rows": {f: {**row, **extra} for f, row in request["rows"].items()},
    }


def exchange(shown: RunsView, request: dict[str, Any]) -> bool:
    return asyncio.run(shown.exchange(request))


def test_first_asks_for_every_run() -> None:
    shown = view()
    shown.update(COLUMNS, {"runs/b": B, "runs/a": A})

    assert shown.next_request() == {
        "columns": COLUMNS,
        "rows": {"runs/a": A, "runs/b": B},
    }
    assert shown.next_request() is None


def test_asks_for_nothing_without_changes() -> None:
    shown = view()

    assert shown.next_request() is None


def test_waits_for_the_reply_before_asking_again() -> None:
    shown = view()
    shown.update(COLUMNS, {"runs/a": A})
    shown.next_request()
    shown.touch("runs/a/stderr.log")

    assert shown.next_request() is None
    shown.busy = False
    assert shown.next_request() == {"columns": COLUMNS, "rows": {"runs/a": A}}


def test_asks_again_only_for_runs_that_changed() -> None:
    shown = view()
    shown.update(COLUMNS, {"runs/a": A, "runs/b": B})
    shown.next_request()
    shown.busy = False
    changed = {**B, "exit_code": 0}

    shown.update(COLUMNS, {"runs/a": A, "runs/b": changed})

    assert shown.next_request() == {"columns": COLUMNS, "rows": {"runs/b": changed}}


def test_asks_for_every_run_when_the_columns_change() -> None:
    shown = view()
    shown.update(COLUMNS, {"runs/a": A, "runs/b": B})
    shown.next_request()
    shown.busy = False
    more = [*COLUMNS, {"key": "m", "label": "m"}]

    shown.update(more, {"runs/a": A, "runs/b": B})

    request = shown.next_request()
    assert request is not None
    assert (request["columns"], list(request["rows"])) == (more, ["runs/a", "runs/b"])


def test_a_file_change_asks_for_the_run_that_holds_it() -> None:
    shown = view()
    folders = ["runs/a", "runs/ab", "runs/a/1"]
    shown.update(COLUMNS, {f: {"folder": f} for f in folders})
    shown.next_request()
    shown.busy = False

    shown.touch("runs/a/1/out/x.txt")
    shown.touch("runs/ab")
    shown.touch("elsewhere/runs/a/y")

    request = shown.next_request()
    assert request is not None
    assert list(request["rows"]) == ["runs/a/1"]


def test_forgets_removed_runs() -> None:
    request = {"columns": COLUMNS, "rows": {"runs/a": A, "runs/b": B}}
    shown = view(answer(request, m=1))
    shown.update(COLUMNS, {"runs/a": A, "runs/b": B})
    exchange(shown, shown.next_request())  # type: ignore[arg-type]
    shown.touch("runs/b/x")

    shown.update(COLUMNS, {"runs/a": A})

    assert shown.next_request() is None
    assert shown.table()[1] == {"runs/a": {**A, "m": 1}}
    assert shown.sent == {"runs/a": A}


def test_shows_native_rows_until_the_view_answers() -> None:
    shown = view()
    shown.update(COLUMNS, {"runs/a": A})

    assert shown.table() == (COLUMNS, {"runs/a": A})


def test_shows_the_view_answer() -> None:
    shown = view({"columns": ["m"], "rows": {"runs/a": {"m": 1}}})
    shown.update(COLUMNS, {"runs/a": A, "runs/b": B})
    shown.next_request()
    shown.native = {"runs/a": A}
    request = {"columns": COLUMNS, "rows": {"runs/a": A}}

    assert exchange(shown, request) is True
    assert shown.table() == ([{"key": "m", "label": "m"}], {"runs/a": {"m": 1}})
    assert shown.busy is False
    assert shown.elapsed == 0.01


def test_shows_an_empty_column_list() -> None:
    request = {"columns": COLUMNS, "rows": {"runs/a": A}}
    shown = view({"columns": [], "rows": {"runs/a": {}}})
    shown.update(COLUMNS, {"runs/a": A})

    exchange(shown, request)

    assert shown.table()[0] == []


def test_reports_no_change_for_the_same_answer() -> None:
    request = {"columns": COLUMNS, "rows": {"runs/a": A}}
    reply = answer(request, m=1)
    again = answer(request, m=2)
    wider = {**again, "columns": [*again["columns"], "n"]}
    shown = view(reply, reply, again, wider)
    shown.update(COLUMNS, {"runs/a": A})

    assert [exchange(shown, request) for _ in range(4)] == [True, False, True, True]


@pytest.mark.parametrize(
    ("reply", "error"),
    [
        ({"columns": []}, "the response must be an object with columns and rows"),
        (OSError("broken pipe"), "broken pipe"),
        (ValueError("the runs view stopped"), "the runs view stopped"),
    ],
)
def test_keeps_the_last_good_rows_on_a_bad_answer(reply: object, error: str) -> None:
    request = {"columns": COLUMNS, "rows": {"runs/a": A}}
    shown = view(answer(request, m=1), reply, answer(request, m=1))
    shown.update(COLUMNS, {"runs/a": A})
    exchange(shown, request)

    assert exchange(shown, request) is False
    assert shown.error == error
    assert shown.busy is False
    assert shown.table()[1] == {"runs/a": {**A, "m": 1}}
    assert shown.status() == f"runs view: {error}"

    exchange(shown, request)
    assert shown.error is None


@pytest.mark.parametrize(
    ("error", "elapsed", "status"),
    [
        (None, None, ""),
        (None, 0.1, ""),
        (None, 0.1404, "runs view took 140 ms"),
        ("bad", 0.05, "runs view: bad"),
        ("bad", 0.2, "runs view: bad · runs view took 200 ms"),
    ],
)
def test_describes_errors_and_slow_answers(
    error: str | None, elapsed: float | None, status: str
) -> None:
    shown = view()
    shown.error, shown.elapsed = error, elapsed

    assert shown.status() == status
