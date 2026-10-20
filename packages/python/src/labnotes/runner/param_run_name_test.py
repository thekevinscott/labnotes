import pytest

from labnotes.runner.param_run_name import param_run_name

PROBLEMS: list[object] = [
    "../data/APPS/test/0580",
    "../data/APPS/test/2002",
    "../data/APPS/test/3876",
]

CASES = [
    pytest.param(
        {"problem-dir": "../data/APPS/test/0580"},
        {"problem-dir": PROBLEMS},
        "0580",
        id="drops-the-shared-path-prefix",
    ),
    pytest.param(
        {"problem-dir": "../data/APPS/test/0580", "U": "mimo"},
        {"problem-dir": PROBLEMS, "U": ["mimo"]},
        "0580",
        id="ignores-params-that-never-change",
    ),
    pytest.param(
        {"U": "mimo", "m": "a"},
        {"U": ["mimo"], "m": ["a", "b"]},
        "a",
        id="looks-past-a-constant-listed-first",
    ),
    pytest.param({"m": "a"}, {"m": ["a"]}, "", id="nothing-varies"),
    pytest.param({}, {}, "", id="no-params"),
    pytest.param(
        {"n": 10}, {"n": [10, 11]}, "10", id="keeps-a-prefix-with-no-separator"
    ),
    pytest.param({"m": "abc"}, {"m": ["abc", "abd"]}, "abc", id="keeps-shared-letters"),
    pytest.param(
        {"m": "run-alpha"},
        {"m": ["run-alpha", "run-beta"]},
        "alpha",
        id="cuts-the-prefix-at-its-last-separator",
    ),
    pytest.param(
        {"m": "a/b-c1"},
        {"m": ["a/b-c1", "a/b-c2"]},
        "c1",
        id="cuts-at-the-last-of-several-separators",
    ),
    pytest.param(
        {"m": "a/x/y"},
        {"m": ["a/x/y", "a/x"]},
        "x-y",
        id="a-value-that-is-a-prefix-of-another",
    ),
    pytest.param(
        {"m": "p/"}, {"m": ["p/", "p/s"]}, "", id="value-is-all-shared-prefix"
    ),
    pytest.param(
        {"a": "p/q", "b": 3},
        {"a": ["p/q", "p/s"], "b": [3, 4]},
        "q-3",
        id="joins-varying-values-with-a-dash",
    ),
    pytest.param(
        {"b": 3, "a": "q"},
        {"a": ["q", "s"], "b": [3, 4]},
        "q-3",
        id="follows-the-config-order-of-params",
    ),
    pytest.param(
        {"a": "p/", "b": 3},
        {"a": ["p/", "p/s"], "b": [3, 4]},
        "3",
        id="skips-an-empty-part-when-joining",
    ),
    pytest.param(
        {"m": "a  b..c"},
        {"m": ["a  b..c", "z"]},
        "a-b-c",
        id="collapses-a-run-of-unsafe-characters",
    ),
    pytest.param({"m": "(foo)"}, {"m": ["(foo)", "z"]}, "foo", id="trims-edge-dashes"),
    pytest.param({"m": "café"}, {"m": ["café", "z"]}, "caf", id="drops-non-ascii"),
    pytest.param({"m": "Big"}, {"m": ["Big", "z"]}, "Big", id="keeps-case"),
    pytest.param({"m": 0.5}, {"m": [0.5, 1.5]}, "0-5", id="number-with-a-dot"),
    pytest.param({"m": True}, {"m": [True, False]}, "True", id="boolean"),
    pytest.param({"m": None}, {"m": [None, 1]}, "None", id="none"),
    pytest.param(
        {"m": "x" * 70},
        {"m": ["x" * 70, "y"]},
        "x" * 60,
        id="cuts-at-sixty-characters",
    ),
    pytest.param(
        {"m": "x" * 59 + "/y"},
        {"m": ["x" * 59 + "/y", "z"]},
        "x" * 59,
        id="trims-a-dash-left-by-the-cut",
    ),
    pytest.param(
        {"m": "x" * 60},
        {"m": ["x" * 60, "y"]},
        "x" * 60,
        id="keeps-exactly-sixty",
    ),
]


@pytest.mark.parametrize(("params", "choices", "name"), CASES)
def test_names_a_run_by_the_params_that_vary(
    params: dict[str, object], choices: dict[str, list[object]], name: str
) -> None:
    assert param_run_name(params, choices) == name
