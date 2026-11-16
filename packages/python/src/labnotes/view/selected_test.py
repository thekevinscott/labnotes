from labnotes.view.selected import Selected


def test_carries_the_selected_run() -> None:
    assert Selected("20261116-000001-quiet-pond").run == "20261116-000001-quiet-pond"
    assert Selected(None).run is None


def test_is_handled_as_on_labnotes_selected_and_bubbles_to_the_app() -> None:
    assert Selected(None).handler_name == "on_labnotes_selected"
    assert Selected.bubble is True
