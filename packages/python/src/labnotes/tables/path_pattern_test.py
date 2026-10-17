import pytest

from labnotes.tables.path_pattern import path_pattern


@pytest.mark.parametrize(
    ("template", "path", "groups"),
    [
        ("{experiment}/runs/{run}", "a/runs/b", {"experiment": "a", "run": "b"}),
        (
            "data/{experiment}/{run}",
            "data/a.b/c-d",
            {"experiment": "a.b", "run": "c-d"},
        ),
        ("{experiment}/files/", "a/files/x/y.md", {"experiment": "a"}),
        ("notes/{experiment}/*.md", "notes/a/plan.md", {"experiment": "a"}),
        ("{experiment}/**", "a/x/y", {"experiment": "a"}),
        ("{experiment}/v?.txt", "a/v1.txt", {"experiment": "a"}),
    ],
)
def test_captures_the_placeholders(
    template: str, path: str, groups: dict[str, str]
) -> None:
    found = path_pattern(template).fullmatch(path)

    assert found is not None
    assert found.groupdict() == groups


@pytest.mark.parametrize(
    ("template", "path"),
    [
        ("{experiment}/runs/{run}", "a/runs/b/c"),
        ("{experiment}/runs/{run}", "a/results/b"),
        ("{experiment}/files/", "a/files/"),
        ("notes/{experiment}/*.md", "notes/a/sub/plan.md"),
        ("notes/{experiment}/*.md", "notes/a/plan.txt"),
        ("a.b/{experiment}", "axb/e"),
    ],
)
def test_rejects_other_paths(template: str, path: str) -> None:
    assert path_pattern(template).fullmatch(path) is None
