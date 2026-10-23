import pytest

from labnotes.tui.native_rows import native_row, native_rows

RUN = {
    "labnotes_completed": 1,
    "labnotes_unfinished": 0,
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
    ("completed", "unfinished", "status"),
    [(1, 0, "passed"), (0, 0, "failed"), (0, 1, "unfinished"), (1, 1, "unfinished")],
)
def test_names_the_status(completed: int, unfinished: int, status: str) -> None:
    run = {**RUN, "labnotes_completed": completed, "labnotes_unfinished": unfinished}

    assert native_row(run)["status"] == status


def test_keys_each_run_by_its_folder() -> None:
    other = {**RUN, "id": "r2", "folder": "alpha/runs/r2"}

    assert native_rows({"runs_list": [RUN, other]}) == {
        "alpha/runs/r1": native_row(RUN),
        "alpha/runs/r2": native_row(other),
    }
