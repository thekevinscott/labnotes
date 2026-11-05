from labnotes.tui.stage_line import stage_line


def test_joins_the_stages_in_order_with_their_marks() -> None:
    line = stage_line(
        [("setup", "passed"), ("runs", "running"), ("teardown", "waiting")], "runs", "/"
    )

    assert line.plain == " setup ✓   ›   runs /   ›   teardown ○ "


def test_marks_a_failed_stage_red() -> None:
    line = stage_line([("setup", "failed"), ("runs", "waiting")], "runs", "|")

    assert [str(span.style) for span in line.spans][0] == "red"


def test_highlights_the_current_stage() -> None:
    line = stage_line([("setup", "running"), ("runs", "waiting")], "setup", "|")

    assert str(line.spans[0].style) == "bold reverse"
    assert line.plain[line.spans[0].start : line.spans[0].end] == " setup | "


def test_highlights_only_the_stage_equal_to_the_current_one() -> None:
    current = "".join(["set", "up"])

    line = stage_line([("runs", "waiting"), ("setup", "running")], current, "|")

    assert [str(span.style) for span in line.spans] == ["dim", "dim", "bold reverse"]
