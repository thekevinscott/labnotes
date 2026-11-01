from labnotes.runner.placeholders import PLACEHOLDERS


def test_names_the_folder_placeholders() -> None:
    assert PLACEHOLDERS == ("run_dir", "invocation_dir")
