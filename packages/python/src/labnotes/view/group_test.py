import dataclasses

import pytest

from labnotes.view.group import Group


def test_holds_the_name_folders_and_flatness() -> None:
    group = Group("inv", ("alpha/runs/inv/a", "alpha/runs/inv/b"), False)

    assert group.name == "inv"
    assert group.folders == ("alpha/runs/inv/a", "alpha/runs/inv/b")
    assert group.flat is False


def test_holds_structure_only() -> None:
    assert [field.name for field in dataclasses.fields(Group)] == [
        "name",
        "folders",
        "flat",
    ]


def test_is_frozen() -> None:
    group = Group("inv", (), True)

    with pytest.raises(dataclasses.FrozenInstanceError):
        group.name = "other"  # type: ignore[misc]
