from labnotes.daemon.sse import sse


def test_sse_frames_json_data_as_one_event() -> None:
    assert sse({"batch": "b", "event": {"at": 1}}) == (
        'data: {"batch": "b", "event": {"at": 1}}\n\n'
    )


def test_sse_names_the_event_when_given() -> None:
    assert sse("Preparing", "step") == 'event: step\ndata: "Preparing"\n\n'


def test_sse_keeps_newlines_inside_one_data_line() -> None:
    assert sse("a\nb") == 'data: "a\\nb"\n\n'


def test_sse_carries_an_id_after_the_name() -> None:
    assert sse([], "state", "ab12") == "event: state\nid: ab12\ndata: []\n\n"
    assert sse(1, id="7") == "id: 7\ndata: 1\n\n"
