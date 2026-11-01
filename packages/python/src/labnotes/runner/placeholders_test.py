from labnotes.runner.placeholders import HOOK_PLACEHOLDERS, PLACEHOLDERS


def test_hooks_get_the_invocation_folder_but_not_the_run_folder() -> None:
    assert (PLACEHOLDERS, HOOK_PLACEHOLDERS) == (
        ("run_dir", "invocation_dir"),
        ("invocation_dir",),
    )
