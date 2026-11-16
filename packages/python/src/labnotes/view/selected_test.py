from labnotes.view.selected import Selected


def test_carries_the_selected_run() -> None:
    assert Selected("a1").run == "a1"
    assert Selected(None).run is None


def test_is_handled_as_on_labnotes_selected_and_does_not_bubble() -> None:
    assert Selected("a1").handler_name == "on_labnotes_selected"
    assert Selected.bubble is False
