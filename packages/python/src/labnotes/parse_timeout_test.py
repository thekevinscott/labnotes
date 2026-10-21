import click
import pytest

from labnotes.parse_timeout import parse_timeout


def parse(value: str | None) -> float | None:
    return parse_timeout(click.Context(click.Command("x")), click.Option(["-t"]), value)


def test_leaves_an_unset_timeout_unset() -> None:
    assert parse(None) is None


@pytest.mark.parametrize(
    ("given", "seconds"),
    [
        ("1", 1),
        ("90", 90),
        ("30s", 30),
        ("10m", 600),
        ("2h", 7200),
        ("1h30m", 5400),
        ("1.5", 1.5),
    ],
)
def test_reads_seconds_or_units(given: str, seconds: float) -> None:
    assert parse(given) == seconds


@pytest.mark.parametrize("given", ["soon", "", "0", "0s", "-5m"])
def test_rejects_anything_but_a_positive_duration(given: str) -> None:
    with pytest.raises(click.BadParameter, match="use a duration over 0"):
        parse(given)
