import pytest

from labnotes.runner.check_hook_placeholders import check_hook_placeholders


def test_accepts_hooks_without_folder_placeholders() -> None:
    check_hook_placeholders({"setup": "up {other}", "teardown": None, "meta": "m"})


@pytest.mark.parametrize("name", ["run_dir", "invocation_dir"])
@pytest.mark.parametrize("hook", ["setup", "teardown", "meta"])
def test_rejects_a_folder_placeholder_in_every_hook(name: str, hook: str) -> None:
    hooks: dict[str, str | None] = {"setup": None, hook: f"down {{{name}}}"}

    with pytest.raises(ValueError) as error:
        check_hook_placeholders(hooks)

    assert str(error.value) == (
        f"{hook} command down {{{name}}} uses {{{name}}}; setup, teardown, "
        "and meta get no folder placeholders. "
        "Share values with set_state() and get_state()."
    )
