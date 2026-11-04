from pathlib import Path

import pytest

from labnotes.read_path import DEFAULT_PATHS, SINGLE_PATHS, read_path

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


@pytest.mark.parametrize(
    "section", [{"mode": "matrix"}, {"concurrency": 2}, {"retries": 0}]
)
def test_lets_settings_through_in_experiments(section: dict[str, object]) -> None:
    assert read_path(CONFIG, "experiments", section) == "{experiment}"


@pytest.mark.parametrize(
    ("table", "section", "message"),
    [
        ("experiments", "e", "experiments must be a table, like [experiments]"),
        ("files", {"glob": 1}, "unknown keys in [files]: glob"),
        ("files", {"mode": "matrix"}, "unknown keys in [files]: mode"),
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


@pytest.mark.parametrize("table", SINGLE_PATHS)
def test_one_experiment_drops_the_experiment_prefix(table: str) -> None:
    assert read_path(CONFIG, table, {}, single=True) == SINGLE_PATHS[table]


@pytest.mark.parametrize(
    ("table", "template"), [("files", "notes/"), ("runs", "outputs/{run}")]
)
def test_one_experiment_reads_a_path_without_experiment(
    table: str, template: str
) -> None:
    assert read_path(CONFIG, table, {"path": template}, single=True) == template


def test_one_experiment_keeps_experiments_settings() -> None:
    assert read_path(CONFIG, "experiments", {"mode": "matrix"}, single=True) == ""


@pytest.mark.parametrize(
    ("table", "section", "message"),
    [
        ("experiments", {"path": "x"}, "[experiments] path doesn't apply"),
        (
            "files",
            {"path": "{experiment}/notes/"},
            "[files] path can't use {experiment}",
        ),
        (
            "runs",
            {"path": "{experiment}/runs/{run}"},
            "[runs] path can't use {experiment}",
        ),
        ("files", {"path": "notes/{run}/"}, "[files] path can't use placeholders"),
        ("runs", {"path": "runs"}, "[runs] path must use exactly {run}"),
    ],
)
def test_one_experiment_rejects_a_bad_path(
    table: str, section: object, message: str
) -> None:
    with pytest.raises(ValueError) as error:
        read_path(CONFIG, table, section, single=True)

    assert str(error.value).startswith(f"{CONFIG}: {message}")
