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


def test_leaves_out_values_using_a_placeholder_it_was_not_given() -> None:
    assert fill_experiment_env(
        {
            "INVOCATION": "{invocation_dir}",
            "BOTH": "{run_dir}/{invocation_dir}",
            "RUN": "{run_dir}",
            "PLAIN": "kept",
        },
        {},
        {"run_dir": "/run"},
    ) == {"RUN": "/run", "PLAIN": "kept"}


def test_ignores_an_overridden_placeholder() -> None:
    assert fill_experiment_env(
        {"LABEL": "{run_dir}"},
        {"LABEL": "caller"},
        {},
    ) == {"LABEL": "caller"}


def test_an_overridden_key_does_not_skip_later_configured_keys() -> None:
    assert fill_experiment_env(
        {"BOTH": "configured", "LATER": "present"},
        {"BOTH": "caller"},
        {},
    ) == {"BOTH": "caller", "LATER": "present"}
