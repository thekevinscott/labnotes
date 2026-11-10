from labnotes.tui.startup_steps import startup_steps


def test_marks_finished_steps_and_spins_the_current_one() -> None:
    shown = startup_steps(["Starting daemon", "Snapshotting repo"], "/")
    assert shown.plain == "✓ Starting daemon\n/ Snapshotting repo\n"


def test_shows_nothing_before_the_first_step() -> None:
    assert startup_steps([], "/").plain == ""
