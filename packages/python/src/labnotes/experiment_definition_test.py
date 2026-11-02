from labnotes.experiment_definition import experiment_definition

TEXT = (
    '# Top.\ncommand = "go"\nrepeats = 2\n\n[params]\n# hint\nm = ["a", "b"]\nn = [1]\n'
)


def test_keeps_the_text_when_nothing_changes() -> None:
    assert experiment_definition(TEXT, None, None, None, {}) == TEXT


def test_replaces_command_repeats_and_named_params() -> None:
    assert experiment_definition(TEXT, None, "run", 5, {"m": ["c"], "k": [True]}) == (
        '# Top.\ncommand = "run"\nrepeats = 5\n\n'
        '[params]\n# hint\nm = ["c"]\nn = [1]\nk = [true]\n'
    )


def test_adds_params_and_settings_a_file_lacks() -> None:
    assert experiment_definition("", None, "go", 3, {"m": ["a"]}) == (
        'command = "go"\nrepeats = 3\n\n[params]\nm = ["a"]\n'
    )


def test_records_where_it_came_from_first() -> None:
    text = 'from = "older"\ncommand = "go"\n'

    assert experiment_definition(text, "sanity-3", None, None, {}) == (
        'from = "sanity-3"\ncommand = "go"\n'
    )
