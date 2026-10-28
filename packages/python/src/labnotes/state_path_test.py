from pathlib import Path

import pytest

from labnotes.state_path import state_path


@pytest.mark.parametrize("writable", [False, True])
def test_reads_the_current_hook_path(
    monkeypatch: pytest.MonkeyPatch, writable: bool
) -> None:
    for value in ("/outer/state.json", "/inner/state.json"):
        monkeypatch.setenv("LABNOTES_STATE", value)
        assert state_path(writable=writable) == Path(value)


@pytest.mark.parametrize("hook", [None, ""])
@pytest.mark.parametrize("run", [None, "", "/invocation/state.json"])
def test_run_state_is_read_only_and_missing_context_raises(
    monkeypatch: pytest.MonkeyPatch, hook: str | None, run: str | None
) -> None:
    for key, value in (("LABNOTES_STATE", hook), ("LABNOTES_RUN_STATE", run)):
        monkeypatch.delenv(key, raising=False)
        if value is not None:
            monkeypatch.setenv(key, value)
    if run:
        assert state_path() == Path(run)
    else:
        with pytest.raises(RuntimeError, match="setup, runs, and teardown"):
            state_path()
    with pytest.raises(RuntimeError, match="only writable in setup and teardown"):
        state_path(writable=True)
