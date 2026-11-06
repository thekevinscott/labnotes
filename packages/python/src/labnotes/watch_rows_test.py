from unittest import mock

from labnotes.watch_rows import watch_rows


def test_starts_watching_before_it_is_iterated() -> None:
    tables = mock.Mock()
    with mock.patch(
        "labnotes.watch_rows.matching_rows", return_value="rows"
    ) as matching_rows:
        rows = watch_rows(tables, {"files"}, "alpha")

    tables.watch.assert_called_once_with()
    matching_rows.assert_called_once_with(tables.watch.return_value, {"files"}, "alpha")
    assert rows == "rows"


def test_watches_every_experiment_by_default() -> None:
    tables = mock.Mock()
    with mock.patch("labnotes.watch_rows.matching_rows") as matching_rows:
        watch_rows(tables, {"files"})

    matching_rows.assert_called_once_with(tables.watch.return_value, {"files"}, None)
