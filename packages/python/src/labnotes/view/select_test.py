from labnotes.view.select import Select


def test_carries_the_run_to_select() -> None:
    assert Select("a1").run == "a1"
    assert Select(None).run is None


def test_is_handled_as_on_labnotes_select_and_bubbles_to_the_tui() -> None:
    assert Select("a1").handler_name == "on_labnotes_select"
    assert Select.bubble is True
