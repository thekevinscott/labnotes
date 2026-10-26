import pytest

from labnotes.runner.check_subset import check_subset

PARAMS: dict[str, list[object]] = {"model": ["small", "large"], "n": [1, 2]}


def test_accepts_declared_values() -> None:
    check_subset(PARAMS, {"model": "large", "n": "2"})


def test_accepts_nothing() -> None:
    check_subset({}, {})


def test_rejects_an_unknown_param() -> None:
    with pytest.raises(ValueError, match=r"^No param size\. Params: model, n\.$"):
        check_subset(PARAMS, {"size": "small"})


def test_names_no_params_when_there_are_none() -> None:
    with pytest.raises(ValueError, match=r"^No param size\. Params: none\.$"):
        check_subset({}, {"size": "small"})


def test_rejects_an_undeclared_value() -> None:
    with pytest.raises(
        ValueError, match=r"^No value medium for model\. Values: small, large\.$"
    ):
        check_subset(PARAMS, {"model": "medium"})


def test_matches_values_by_their_string_form() -> None:
    with pytest.raises(ValueError, match=r"^No value 3 for n\. Values: 1, 2\.$"):
        check_subset(PARAMS, {"n": "3"})
