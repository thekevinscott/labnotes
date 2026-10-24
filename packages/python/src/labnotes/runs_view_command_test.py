import pytest

from labnotes.runs_view_command import runs_view_command


@pytest.mark.parametrize(
    ("config", "command"),
    [
        ({"views": {"runs": "uv run view.py"}}, "uv run view.py"),
        ({"views": {"runs": " "}}, None),
        ({"views": {"runs": 1}}, None),
        ({"views": {}}, None),
        ({"views": "x"}, None),
        ({}, None),
        (None, None),
    ],
)
def test_reads_the_runs_view_command(
    config: dict[str, object] | None, command: str | None
) -> None:
    assert runs_view_command(config) == command
