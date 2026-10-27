import pytest

from labnotes.runner.fill_experiment_env import fill_experiment_env


def test_fills_config_values_without_quoting_and_keeps_caller_precedence() -> None:
    assert fill_experiment_env(
        {
            "PATH_VALUE": "{run_dir} {run_id} {invocation_id}",
            "BOTH": "configured",
        },
        {"BOTH": "caller", "LABNOTES_RUN": "wrong"},
        {"run_dir": "/a b", "run_id": "g/a", "invocation_id": "g"},
    ) == {"PATH_VALUE": "/a b g/a g", "BOTH": "caller"}


def test_rejects_a_hook_value_needing_an_unavailable_run_id() -> None:
    with pytest.raises(ValueError) as error:
        fill_experiment_env(
            {"LABEL": "{run_id}"},
            {},
            {"invocation_id": "g"},
            hook="setup",
            runs=2,
        )
    assert str(error.value) == (
        "setup env.LABEL uses {run_id}, but this invocation plans 2 runs. "
        "{run_id} needs exactly one; use {invocation_id} instead."
    )


def test_rejects_a_hook_value_needing_an_unavailable_run_dir() -> None:
    with pytest.raises(ValueError, match=r"teardown env.LABEL uses \{run_dir\}"):
        fill_experiment_env(
            {"LABEL": "{run_dir}"},
            {},
            {"invocation_id": "g"},
            hook="teardown",
            runs=0,
        )


def test_ignores_an_overridden_placeholder() -> None:
    assert fill_experiment_env(
        {"LABEL": "{run_id}"},
        {"LABEL": "caller"},
        {"invocation_id": "g"},
        hook="meta",
        runs=2,
    ) == {"LABEL": "caller"}
