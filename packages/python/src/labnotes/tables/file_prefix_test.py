import pytest

from labnotes.tables.file_prefix import file_prefix


@pytest.mark.parametrize(
    ("template", "prefix"),
    [
        ("{experiment}/files/", "{experiment}/files/"),
        ("notes/{experiment}/*.md", "notes/{experiment}/"),
        ("{experiment}/docs/**/*.md", "{experiment}/docs/"),
        ("{experiment}/notes.md", "{experiment}/"),
        ("{experiment}/n?tes.md", "{experiment}/"),
        ("a/b*.md", "a/"),
    ],
)
def test_is_the_folder_before_the_first_wildcard(template: str, prefix: str) -> None:
    assert file_prefix(template) == prefix
