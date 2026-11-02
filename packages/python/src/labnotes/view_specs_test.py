import pytest

from labnotes.view_specs import view_specs


@pytest.mark.parametrize(
    ("config", "specs"),
    [
        (
            {"views": {"b": "b.py:B", "runs": "uv run v.py", "a": "a.py:A"}},
            {"b": "b.py:B", "a": "a.py:A"},
        ),
        ({"views": {"a": 1}}, {}),
        ({"views": "x"}, {}),
        ({}, {}),
        (None, {}),
    ],
)
def test_names_the_views_in_config_order(
    config: dict[str, object] | None, specs: dict[str, str]
) -> None:
    assert list(view_specs(config).items()) == list(specs.items())
