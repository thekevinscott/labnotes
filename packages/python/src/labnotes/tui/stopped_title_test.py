from labnotes.tui.stopped_title import stopped_title


def test_appends_the_error_to_the_title() -> None:
    assert (
        stopped_title("alpha", OSError("watcher died"))
        == "alpha · Live updates stopped: watcher died"
    )


def test_stands_alone_without_a_title() -> None:
    assert stopped_title("", OSError("gone")) == "Live updates stopped: gone"


def test_says_so_when_the_stream_just_ends() -> None:
    assert stopped_title("alpha", None) == "alpha · Live updates stopped."
