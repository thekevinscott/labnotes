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
