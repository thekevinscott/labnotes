from labnotes.study_runs import study_runs


def test_selects_a_studys_runs() -> None:
    assert study_runs("it's") == "(SELECT * FROM runs WHERE study = 'it''s')"
