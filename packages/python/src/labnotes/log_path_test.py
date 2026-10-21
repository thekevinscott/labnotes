from pathlib import Path

import pytest

from labnotes.log_path import LOG_ENV, log_path


def test_reads_the_runner_log_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LABNOTES_LOG", "/runs/a/log.jsonl")

    assert LOG_ENV == "LABNOTES_LOG"
    assert log_path() == Path("/runs/a/log.jsonl")


@pytest.mark.parametrize("value", [None, ""])
def test_is_none_outside_a_run(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("LABNOTES_LOG", raising=False)
    else:
        monkeypatch.setenv("LABNOTES_LOG", value)

    assert log_path() is None
