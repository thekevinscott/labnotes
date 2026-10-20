import asyncio
import json
from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.list_experiments import list_experiments


COMPUTED = (
    "strftime('%Y-%m-%d %H:%M:%S', created) AS started,"
    " CAST(round((julianday(ended) - julianday(created)) * 86400) AS INTEGER)"
    " AS duration"
)


@pytest.fixture
def experiment_progress() -> Iterator[mock.AsyncMock]:
    with mock.patch(
        "labnotes.list_experiments.experiment_progress",
        new_callable=mock.AsyncMock,
        return_value={"runs": 5, "filled": 4},
    ) as patched:
        yield patched


@pytest.fixture(autouse=True)
def check_counts() -> Iterator[mock.AsyncMock]:
    with mock.patch(
        "labnotes.list_experiments.check_counts",
        new_callable=mock.AsyncMock,
        side_effect=lambda tables, source, summary: {**summary, "checked": True},
    ) as patched:
        yield patched


def test_lists_each_experiment_with_its_config_summary_and_progress(
    experiment_progress: mock.AsyncMock,
) -> None:
    config = {"command": "go", "repeats": 2, "mode": "fill", "params": {"x": [1, 2]}}
    tables = mock.Mock()
    tables.query = mock.AsyncMock(
        return_value=[
            {"name": "a", "display_name": "Alpha", "config": json.dumps(config)},
            {"name": "b", "display_name": "b", "config": None},
        ]
    )

    [a, b] = asyncio.run(list_experiments(tables, "adhoc"))

    assert tables.query.await_args.args[0] == (
        "SELECT name, display_name, config FROM experiments ORDER BY name"
    )
    assert (a["name"], a["display_name"], a["target"], a["runs"], a["filled"]) == (
        "a",
        "Alpha",
        4,
        5,
        4,
    )
    assert (b["name"], b["target"]) == ("b", None)
    first, second = experiment_progress.await_args_list
    assert first.args[0] is tables
    assert first.args[1] == (
        '(SELECT *, params ->> \'$."x"\' AS "x", ' + COMPUTED + " FROM runs"
        " WHERE experiment = 'a')"
    )
    assert first.args[2]["target"] == 4
    assert first.args[2]["checked"]
    assert a["checked"]
    assert second.args[1] == (
        "(SELECT *, " + COMPUTED + " FROM runs WHERE experiment = 'b')"
    )
