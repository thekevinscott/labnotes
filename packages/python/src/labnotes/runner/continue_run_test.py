from typing import cast

from labnotes.runner.continue_run import continue_run


def invocations(run: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], run["invocations"])


RUN: dict[str, object] = {
    "params": {"m": "a"},
    "command": "go --m a",
    "created": "2026-10-18T00:00:00Z",
    "ended": None,
    "exit_code": None,
    "git": {"commit": "new", "dirty": False},
}
NEXT: dict[str, object] = {"started": "2026-10-18T00:00:00Z", "stdout": "stdout-2.txt"}


def test_starts_the_list_on_a_first_invocation() -> None:
    assert continue_run({}, RUN, NEXT) == {**RUN, "invocations": [NEXT]}


def test_appends_to_the_invocations_and_keeps_when_the_run_was_created() -> None:
    first = {"started": "2026-10-17T00:00:00Z", "exit_code": 1}
    previous = {
        **RUN,
        "created": "2026-10-17T00:00:00Z",
        "exit_code": 1,
        "args": ["--memory", "8g"],
        "meta": {"m": 1},
        "pid": 7,
        "pid_created": 1.5,
        "note": "mine",
        "invocations": [first],
    }

    run = continue_run(previous, RUN, NEXT)

    assert run == {
        **RUN,
        "created": "2026-10-17T00:00:00Z",
        "note": "mine",
        "invocations": [first, NEXT],
    }


def test_turns_a_run_from_before_continues_into_its_first_invocation() -> None:
    previous = {
        **RUN,
        "created": "2026-10-17T00:00:00Z",
        "ended": "2026-10-17T01:00:00Z",
        "exit_code": 1,
        "ended_by": "signal",
        "error": None,
        "git": {"commit": "old", "dirty": True},
        "args": ["--memory", "8g"],
    }

    first = invocations(continue_run(previous, RUN, NEXT))[0]

    assert first == {
        "started": "2026-10-17T00:00:00Z",
        "ended": "2026-10-17T01:00:00Z",
        "exit_code": 1,
        "ended_by": "signal",
        "error": None,
        "git": "old",
        "args": ["--memory", "8g"],
        "stdout": "stdout.log",
        "stderr": "stderr.log",
    }


def test_records_no_commit_or_args_when_there_were_none() -> None:
    previous: dict[str, object] = {"created": "2026-10-17T00:00:00Z", "git": None}

    first = invocations(continue_run(previous, RUN, NEXT))[0]

    assert (first["git"], first["args"], first["ended_by"]) == (None, [], None)
