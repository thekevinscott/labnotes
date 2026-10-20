from pathlib import Path

import pytest

from labnotes.read_path import DEFAULT_PATHS, read_path

CONFIG = Path("/p/.labnotes.toml")


@pytest.mark.parametrize("table", DEFAULT_PATHS)
def test_a_missing_path_keeps_its_default(table: str) -> None:
    assert read_path(CONFIG, table, {}) == DEFAULT_PATHS[table]


@pytest.mark.parametrize(
    ("table", "template"),
    [
        ("experiments", "notes/{experiment}"),
        ("files", "notes/{experiment}/*.md"),
        ("runs", "data/{experiment}/{run}"),
        ("runs", "{experiment}/results/{run}"),
    ],
)
def test_reads_a_path(table: str, template: str) -> None:
    assert read_path(CONFIG, table, {"path": template}) == template


def test_lets_mode_through_in_experiments() -> None:
    assert read_path(CONFIG, "experiments", {"mode": "fill"}) == "{experiment}"


@pytest.mark.parametrize(
    ("table", "section", "message"),
    [
        ("experiments", "e", "experiments must be a table, like [experiments]"),
        ("files", {"glob": 1}, "unknown keys in [files]: glob"),
        ("files", {"mode": "fill"}, "unknown keys in [files]: mode"),
        ("files", {"path": 1}, "[files] path must be a string"),
        ("files", {"path": "/abs/{experiment}"}, "[files] path must be relative"),
        ("files", {"path": "~/{experiment}"}, "[files] path must be relative"),
        ("files", {"path": "files"}, "[files] path must use exactly {experiment}"),
        (
            "experiments",
            {"path": "{experiment}/{run}"},
            "[experiments] path must use exactly {experiment}",
        ),
        (
            "runs",
            {"path": "{experiment}/runs"},
            "[runs] path must use exactly {experiment} and {run}",
        ),
        (
            "runs",
            {"path": "{experiment}/{run}/{seed}"},
            "[runs] path must use exactly {experiment} and {run}",
        ),
    ],
)
def test_rejects_a_bad_path(table: str, section: object, message: str) -> None:
    with pytest.raises(ValueError) as error:
        read_path(CONFIG, table, section)

    assert str(error.value).startswith(f"{CONFIG}: ")
    assert message in str(error.value)
