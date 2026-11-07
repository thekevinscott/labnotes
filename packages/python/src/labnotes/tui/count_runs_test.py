import pytest

from labnotes.tui.count_runs import count_runs


@pytest.mark.parametrize(
    ("count", "text"), [(0, "0 runs"), (1, "1 run"), (2, "2 runs")]
)
def test_counts_runs_in_the_singular_only_for_one(count: int, text: str) -> None:
    assert count_runs(count) == text
