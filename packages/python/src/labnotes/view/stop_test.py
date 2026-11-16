from labnotes.view.stop import Stop


def test_carries_the_run_to_stop() -> None:
    assert Stop("a1").run == "a1"


def test_is_handled_as_on_labnotes_stop_and_bubbles_to_the_tui() -> None:
    assert Stop("a1").handler_name == "on_labnotes_stop"
    assert Stop.bubble is True
