import pytest

from labnotes.tables.path_glob import path_glob


@pytest.mark.parametrize(
    ("template", "glob"),
    [
        ("{experiment}", "*"),
        ("{experiment}/files/", "*/files/**"),
        ("{experiment}/runs/{run}/run.json", "*/runs/*/run.json"),
        ("notes/{experiment}/*.md", "notes/*/*.md"),
    ],
)
def test_replaces_each_placeholder_with_a_wildcard(template: str, glob: str) -> None:
    assert path_glob(template) == glob
