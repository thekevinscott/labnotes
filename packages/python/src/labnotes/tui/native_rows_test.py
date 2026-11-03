import pytest

from labnotes.tui.native_rows import native_row, native_rows

RUN = {
    "labnotes_completed": 1,
    "labnotes_unfinished": 0,
    "labnotes_running": False,
    "experiment": "alpha",
    "id": "r1",
    "folder": "alpha/runs/r1",
    "created": "2026-10-17T00:00:01.000Z",
    "ended": None,
    "exit_code": 0,
    "params": '{"m": "a"}',
    "run": '{"params": {"m": "a"}}',
    "m": "a",
    "started": "2026-10-17 00:00:01",
    "duration": 5,
}


def test_sends_raw_values_with_json_decoded() -> None:
    assert native_row(RUN) == {
        "status": "passed",
        "experiment": "alpha",
        "id": "r1",
        "folder": "alpha/runs/r1",
        "created": "2026-10-17T00:00:01.000Z",
        "ended": None,
        "exit_code": 0,
        "params": {"m": "a"},
        "run": {"params": {"m": "a"}},
        "m": "a",
        "started": "2026-10-17T00:00:01.000Z",
        "duration": 5,
    }


def test_decodes_meta_when_the_runs_table_has_it() -> None:
    assert native_row({**RUN, "meta": '{"commit": "abc"}'})["meta"] == {"commit": "abc"}
    assert native_row({**RUN, "meta": None})["meta"] is None


@pytest.mark.parametrize(
    ("completed", "unfinished", "running", "status"),
    [
        (1, 0, False, "passed"),
        (0, 0, False, "failed"),
        (0, 1, False, "unfinished"),
        (1, 1, False, "unfinished"),
        (0, 1, True, "running"),
        (1, 1, True, "running"),
    ],
)
def test_names_the_status(
    completed: int, unfinished: int, running: bool, status: str
) -> None:
    run = {
        **RUN,
        "labnotes_completed": completed,
        "labnotes_unfinished": unfinished,
        "labnotes_running": running,
    }

    assert native_row(run)["status"] == status


def test_lists_runs_flat_in_order_including_old_nested_ones() -> None:
    nested = {**RUN, "id": "inv/r2", "folder": "alpha/runs/inv/r2"}

    assert native_rows({"runs_list": [nested, RUN]}) == (
        native_row(nested),
        native_row(RUN),
    )
