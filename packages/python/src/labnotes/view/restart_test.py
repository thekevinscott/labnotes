from labnotes.view.restart import Restart


def test_carries_the_run_to_restart() -> None:
    assert Restart("a1").run == "a1"


def test_is_handled_as_on_labnotes_restart_and_bubbles_to_the_tui() -> None:
    assert Restart("a1").handler_name == "on_labnotes_restart"
    assert Restart.bubble is True
