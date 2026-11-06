from labnotes.runner.first_invocation import first_invocation


def test_turns_a_run_from_before_continues_into_its_first_invocation() -> None:
    previous = {
        "params": {"m": "a"},
        "created": "2026-10-17T00:00:00Z",
        "ended": "2026-10-17T01:00:00Z",
        "exit_code": 1,
        "ended_by": "signal",
        "error": None,
        "git": {"commit": "old", "dirty": True},
        "args": ["--memory", "8g"],
        "labnotes_version": "1.2.0",
        "labnotes_command": "labnotes experiments exp run",
    }

    assert first_invocation(previous) == {
        "started": "2026-10-17T00:00:00Z",
        "ended": "2026-10-17T01:00:00Z",
        "exit_code": 1,
        "ended_by": "signal",
        "error": None,
        "git": "old",
        "dirty": True,
        "patch": "git-diff.patch",
        "args": ["--memory", "8g"],
        "labnotes_version": "1.2.0",
        "labnotes_command": "labnotes experiments exp run",
        "stdout": "stdout.log",
        "stderr": "stderr.log",
    }


def test_records_no_commit_or_args_when_there_were_none() -> None:
    first = first_invocation({"created": "2026-10-17T00:00:00Z", "git": None})

    assert (first["git"], first["args"], first["ended_by"]) == (None, [], None)
    assert (first["dirty"], first["patch"]) == (None, None)
    assert (first["labnotes_version"], first["labnotes_command"]) == (None, None)
