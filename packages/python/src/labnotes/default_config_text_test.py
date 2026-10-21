from unittest import mock

from labnotes.default_config_text import default_config_text


def test_writes_one_table_per_path() -> None:
    with mock.patch.dict(
        "labnotes.default_config_text.DEFAULT_PATHS",
        {"a": "{experiment}", "b": "{experiment}/{run}"},
        clear=True,
    ):
        assert default_config_text() == (
            '[a]\npath = "{experiment}"\n\n[b]\npath = "{experiment}/{run}"\n'
        )


def test_one_experiment_writes_the_paths_it_can_set() -> None:
    assert default_config_text(single=True) == (
        '[files]\npath = "files/"\n\n[runs]\npath = "runs/{run}"\n'
    )
