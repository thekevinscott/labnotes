from labnotes.runner.fill_ids import fill_ids


def test_fills_every_placeholder_shell_quoted() -> None:
    command = "study {run_id} --group {invocation_id} {run_id}"

    assert fill_ids(command, {"run_id": "g/a b", "invocation_id": "g"}) == (
        "study 'g/a b' --group g 'g/a b'"
    )


def test_leaves_placeholders_without_a_value() -> None:
    assert fill_ids("study {run_id} {run_dir}", {"invocation_id": "g"}) == (
        "study {run_id} {run_dir}"
    )


def test_fills_environment_values_without_shell_quoting() -> None:
    assert (
        fill_ids(
            "prefix {run_dir} {run_id}",
            {"run_dir": "/a b", "run_id": "g/a"},
            quote=False,
        )
        == "prefix /a b g/a"
    )
