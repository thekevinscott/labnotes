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
def count_runs() -> Iterator[mock.AsyncMock]:
    with mock.patch(
        "labnotes.list_experiments.count_runs",
        new_callable=mock.AsyncMock,
        return_value=[{"runs": 5, "completed": 4}],
    ) as patched:
        yield patched


@pytest.fixture(autouse=True)
def check_counts() -> Iterator[mock.AsyncMock]:
    with mock.patch(
        "labnotes.list_experiments.check_counts",
        new_callable=mock.AsyncMock,
        side_effect=lambda tables, source, summary: {
            **summary,
            "completed_run": "checked",
        },
    ) as patched:
        yield patched


def test_lists_each_experiment_with_its_config_summary_and_run_counts(
    count_runs: mock.AsyncMock,
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
    assert (a["name"], a["display_name"], a["mode"], a["runs"], a["completed"]) == (
        "a",
        "Alpha",
        "fill",
        5,
        4,
    )
    assert (b["name"], b["mode"]) == ("b", "adhoc")
    first, second = count_runs.await_args_list
    assert first.args[0] is tables
    assert first.args[1] == (
        '(SELECT *, params ->> \'$."x"\' AS "x", ' + COMPUTED + " FROM runs"
        " WHERE experiment = 'a')"
    )
    assert first.args[2] == "checked"
    assert a["completed_run"] == "checked"
    assert second.args[1] == (
        "(SELECT *, " + COMPUTED + " FROM runs WHERE experiment = 'b')"
    )
