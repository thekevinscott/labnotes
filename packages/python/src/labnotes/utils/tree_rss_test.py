from unittest import mock

from labnotes.utils.tree_rss import tree_rss


def test_gives_the_trees_resident_memory() -> None:
    with mock.patch(
        "labnotes.utils.tree_rss.tree_usage", return_value=(123, 3)
    ) as tree_usage:
        assert tree_rss(7, 50.0) == 123
    tree_usage.assert_called_once_with(7, 50.0)


def test_has_nothing_when_the_tree_has_no_usage() -> None:
    with mock.patch("labnotes.utils.tree_rss.tree_usage", return_value=None):
        assert tree_rss(7, 50.0) is None
