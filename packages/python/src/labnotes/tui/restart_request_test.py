from pathlib import Path

import pytest

from labnotes.tui.restart_request import restart_request


def test_sends_the_clients_environment_and_experiment_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LABNOTES_RESTART_PROBE", "client")

    request = restart_request("r1", Path("/project/other.toml"))

    assert request["command"] == "restart"
    options = request["options"]
    assert isinstance(options, dict)
    assert options["run_id"] == "r1"
    assert options["experiment_config"] == "/project/other.toml"
    assert options["environment"]["LABNOTES_RESTART_PROBE"] == "client"


def test_copies_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LABNOTES_RESTART_PROBE", "before")
    request = restart_request("r1", None)
    monkeypatch.setenv("LABNOTES_RESTART_PROBE", "after")

    options = request["options"]
    assert isinstance(options, dict)
    assert options["experiment_config"] is None
    assert options["environment"]["LABNOTES_RESTART_PROBE"] == "before"
