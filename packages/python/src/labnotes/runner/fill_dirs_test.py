from inspect import Parameter, signature

from labnotes.runner.fill_dirs import fill_dirs


def test_fills_every_placeholder_shell_quoted() -> None:
    command = "study {run_dir} --group {invocation_dir} {run_dir}"

    assert fill_dirs(command, {"run_dir": "/a b/run", "invocation_dir": "/a b"}) == (
        "study '/a b/run' --group '/a b' '/a b/run'"
    )


def test_leaves_placeholders_without_a_value() -> None:
    assert fill_dirs("study {run_dir} {invocation_dir}", {}) == (
        "study {run_dir} {invocation_dir}"
    )


def test_fills_environment_values_without_shell_quoting() -> None:
    assert (
        fill_dirs(
            "prefix {run_dir} {invocation_dir}",
            {"run_dir": "/a b/run", "invocation_dir": "/a b"},
            quote=False,
        )
        == "prefix /a b/run /a b"
    )


def test_quote_is_keyword_only() -> None:
    assert signature(fill_dirs).parameters["quote"].kind is Parameter.KEYWORD_ONLY
