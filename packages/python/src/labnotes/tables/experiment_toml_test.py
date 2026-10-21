import pytest

from labnotes.tables.experiment_toml import experiment_toml


@pytest.mark.parametrize(
    ("template", "path"),
    [("{experiment}", "{experiment}/experiment.toml"), ("", "experiment.toml")],
)
def test_names_the_experiment_toml_under_the_template(template: str, path: str) -> None:
    assert experiment_toml(template) == path
