from inspect import Parameter, signature

import pytest

from labnotes.runner.fill_experiment_env import fill_experiment_env


def test_fills_config_values_without_quoting_and_keeps_caller_precedence() -> None:
    assert fill_experiment_env(
        {
            "PATH_VALUE": "{run_dir} {invocation_dir}",
            "BOTH": "configured",
        },
        {"BOTH": "caller", "LABNOTES_RUN": "wrong"},
        {"run_dir": "/a b/run", "invocation_dir": "/a b"},
    ) == {"PATH_VALUE": "/a b/run /a b", "BOTH": "caller"}


@pytest.mark.parametrize("runs", [1, 2])
def test_rejects_run_dir_in_hook_environment(runs: int) -> None:
    with pytest.raises(ValueError) as error:
        fill_experiment_env(
            {"LABEL": "{run_dir}"},
            {},
            {"invocation_dir": "/group"},
            hook="setup",
            runs=runs,
        )
    assert str(error.value) == (
        "setup env.LABEL uses {run_dir}; use {invocation_dir} instead."
    )


def test_rejects_a_matrix_hook_value_needing_invocation_dir() -> None:
    with pytest.raises(ValueError, match=r"teardown env.LABEL uses \{invocation_dir\}"):
        fill_experiment_env(
            {"LABEL": "{invocation_dir}"},
            {},
            {},
            hook="teardown",
            runs=0,
        )


def test_ignores_an_overridden_placeholder() -> None:
    assert fill_experiment_env(
        {"LABEL": "{run_dir}"},
        {"LABEL": "caller"},
        {"invocation_dir": "/group"},
        hook="meta",
        runs=2,
    ) == {"LABEL": "caller"}


def test_an_overridden_key_does_not_skip_later_configured_keys() -> None:
    assert fill_experiment_env(
        {"BOTH": "configured", "LATER": "present"},
        {"BOTH": "caller"},
        {"invocation_dir": "/group"},
    ) == {"BOTH": "caller", "LATER": "present"}


def test_hook_and_run_count_are_keyword_only() -> None:
    parameters = signature(fill_experiment_env).parameters
    assert parameters["hook"].kind is Parameter.KEYWORD_ONLY
    assert parameters["runs"].kind is Parameter.KEYWORD_ONLY
    assert parameters["runs"].default == 1
