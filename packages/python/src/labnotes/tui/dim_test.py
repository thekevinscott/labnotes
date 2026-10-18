from labnotes.tui.dim import dim


def test_grays_the_text() -> None:
    text = dim("pending")

    assert (text.plain, text.style) == ("pending", "dim")
