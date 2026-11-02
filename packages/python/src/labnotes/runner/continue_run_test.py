from unittest import mock

from labnotes.runner.continue_run import continue_run


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
    previous = {**RUN, "exit_code": 1}

    with mock.patch(
        "labnotes.runner.continue_run.first_invocation", return_value={"old": 1}
    ) as first:
        run = continue_run(previous, RUN, NEXT)

    first.assert_called_once_with(previous)
    assert run["invocations"] == [{"old": 1}, NEXT]
