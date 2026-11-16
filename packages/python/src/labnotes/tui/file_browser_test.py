import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest import mock

from labnotes.tui.file_browser import FileBrowser

MISSING = object()


def widgets() -> dict[str, mock.Mock]:
    return {
        name: mock.Mock(name=name)
        for name in ("#files", "#tail", "#files-title", "#tail-title")
    }


def host(**attrs: Any) -> mock.Mock:
    found = widgets()
    browser = mock.Mock(**attrs)
    browser.query_one.side_effect = lambda name, kind=None: found[name]
    browser.found = found
    return browser


def daemon(*events: Any) -> mock.Mock:
    routes: list[str] = []

    async def follow(route: str) -> AsyncIterator[tuple[str, Any]]:
        routes.append(route)
        for event in events:
            if event is MISSING:
                raise ValueError("Not found")
            yield event

    return mock.Mock(follow=follow, routes=routes)


def test_keeps_at_most_ten_thousand_lines() -> None:
    assert FileBrowser.MAX_LINES == 10_000


def test_composes_a_file_list_beside_a_tail() -> None:
    with (
        mock.patch("labnotes.tui.file_browser.Vertical"),
        mock.patch("labnotes.tui.file_browser.Static") as static,
        mock.patch("labnotes.tui.file_browser.DataTable") as table,
        mock.patch("labnotes.tui.file_browser.Log") as log,
    ):
        shown = list(FileBrowser.compose(mock.Mock(MAX_LINES=7)))

    assert len(shown) == 4
    table.assert_called_once_with(id="files", cursor_type="row")
    log.assert_called_once_with(id="tail", max_lines=7)
    assert static.call_args_list == [
        mock.call("Select a run to see its files.", id="files-title"),
        mock.call(id="tail-title"),
    ]


def test_mount_adds_name_and_size_columns() -> None:
    browser = host()

    FileBrowser.on_mount(browser)

    assert browser.found["#files"].add_column.call_args_list == [
        mock.call("name", key="name"),
        mock.call("size", key="size"),
    ]


def test_changed_keeps_the_daemon_and_the_run_ids() -> None:
    browser = host(run=None, listed=None, daemon=None)
    source = mock.Mock()
    experiment = mock.Mock(runs=({"id": "a"}, {"id": 2}))

    FileBrowser.on_labnotes_changed(
        browser, mock.Mock(experiment=experiment, daemon=source)
    )
    FileBrowser.on_labnotes_changed(browser, mock.Mock(experiment=None, daemon=None))

    assert browser.daemon is source
    assert browser.runs == frozenset({"a", "2"})
    browser.list_run.assert_not_called()


def test_changed_lists_a_selected_run_once_it_exists() -> None:
    browser = host(run="a", listed=None, runs=frozenset())

    FileBrowser.on_labnotes_changed(
        browser, mock.Mock(experiment=mock.Mock(runs=()), daemon=None)
    )
    browser.list_run.assert_not_called()
    FileBrowser.on_labnotes_changed(
        browser, mock.Mock(experiment=mock.Mock(runs=({"id": "a"},)), daemon=None)
    )
    browser.list_run.assert_called_once_with()


def test_changed_leaves_an_already_listed_run_alone() -> None:
    browser = host(run="a", listed="a")

    FileBrowser.on_labnotes_changed(
        browser, mock.Mock(experiment=mock.Mock(runs=({"id": "a"},)), daemon=None)
    )

    browser.list_run.assert_not_called()


def test_selected_lists_a_newly_selected_run_only() -> None:
    browser = host(run="a")
    message = mock.Mock(run="a")

    FileBrowser.on_labnotes_selected(browser, message)
    browser.list_run.assert_not_called()
    FileBrowser.on_labnotes_selected(browser, mock.Mock(run="b"))

    assert browser.run == "b"
    browser.list_run.assert_called_once_with()


def test_list_run_waits_for_the_daemon() -> None:
    browser = host(daemon=None, run="a")

    FileBrowser.list_run(browser)

    browser.run_worker.assert_not_called()
    browser.query_one.assert_not_called()


def test_list_run_with_no_run_asks_for_one() -> None:
    browser = host(daemon=mock.Mock(), run=None)

    FileBrowser.list_run(browser)

    browser.found["#files-title"].update.assert_called_once_with(
        "Select a run to see its files."
    )
    browser.run_worker.assert_not_called()


def test_list_run_restarts_both_follows_for_the_run() -> None:
    source = mock.Mock()
    browser = host(daemon=source, run="a")

    FileBrowser.list_run(browser)

    assert browser.listed == "a"
    assert browser.workers.cancel_group.call_args_list == [
        mock.call(browser, "files"),
        mock.call(browser, "tail"),
    ]
    browser.found["#files"].clear.assert_called_once_with()
    browser.found["#tail"].clear.assert_called_once_with()
    browser.found["#tail-title"].update.assert_called_once_with("")
    browser.found["#files-title"].update.assert_called_once_with("Files in a")
    browser.follow_files.assert_called_once_with(source, "a")
    browser.run_worker.assert_called_once_with(
        browser.follow_files.return_value,
        group="files",
        exclusive=True,
        exit_on_error=False,
    )


def test_follow_files_fills_and_updates_the_table() -> None:
    browser = host()
    table = browser.found["#files"]
    table.rows = {"run.json": object()}
    source = daemon(
        ("state", [{"name": "run.json", "size": 10}, {"name": "my log", "size": 2000}]),
        ("file", {"name": "new.log", "size": 1}),
        ("remove", {"name": "run.json"}),
        ("remove", {"name": "never.log"}),
        ("other", {}),
    )

    asyncio.run(FileBrowser.follow_files(browser, source, "a b"))

    assert source.routes == ["/runs/a%20b/files"]
    table.clear.assert_called_once_with()
    assert table.add_row.call_args_list == [
        mock.call("run.json", "10 bytes", key="run.json"),
        mock.call("my log", "2.0 kB", key="my log"),
    ]
    browser.put.assert_called_once_with({"name": "new.log", "size": 1})
    table.remove_row.assert_called_once_with("run.json")


def test_follow_files_says_when_the_run_has_no_folder_yet() -> None:
    browser = host(listed="a")

    asyncio.run(FileBrowser.follow_files(browser, daemon(MISSING), "a"))

    assert browser.listed is None
    browser.found["#files-title"].update.assert_called_once_with("No files yet in a.")


def test_put_updates_the_size_of_a_listed_file() -> None:
    browser = host()
    table = browser.found["#files"]
    table.rows = {"a.log": object()}

    FileBrowser.put(browser, {"name": "a.log", "size": 2000})

    table.update_cell.assert_called_once_with(
        "a.log", "size", "2.0 kB", update_width=True
    )
    table.add_row.assert_not_called()


def test_put_sorts_a_new_file_in_and_keeps_the_cursor_on_its_file() -> None:
    browser = host()
    table = browser.found["#files"]
    table.rows = {"b.log": object()}
    table.row_count = 1
    table.coordinate_to_cell_key.return_value.row_key = "b.log"
    table.get_row_index.return_value = 1

    FileBrowser.put(browser, {"name": "a.log", "size": 1})

    table.coordinate_to_cell_key.assert_called_once_with(table.cursor_coordinate)
    table.add_row.assert_called_once_with("a.log", "1 byte", key="a.log")
    table.sort.assert_called_once_with("name")
    table.get_row_index.assert_called_once_with("b.log")
    table.move_cursor.assert_called_once_with(row=1, animate=False)


def test_put_into_an_empty_table_leaves_the_cursor() -> None:
    browser = host()
    table = browser.found["#files"]
    table.rows = {}
    table.row_count = 0

    FileBrowser.put(browser, {"name": "a.log", "size": 1})

    table.add_row.assert_called_once_with("a.log", "1 byte", key="a.log")
    table.move_cursor.assert_not_called()


def test_choosing_a_file_without_a_run_does_nothing() -> None:
    for attrs in ({"daemon": None, "run": "a"}, {"daemon": mock.Mock(), "run": None}):
        browser = host(**attrs)
        event = mock.Mock()

        FileBrowser.on_data_table_row_selected(browser, event)

        event.stop.assert_called_once_with()
        browser.run_worker.assert_not_called()


def test_choosing_a_file_tails_it() -> None:
    source = mock.Mock()
    browser = host(daemon=source, run="a")
    event = mock.Mock()
    event.row_key.value = "stdout.log"

    FileBrowser.on_data_table_row_selected(browser, event)

    browser.found["#tail"].clear.assert_called_once_with()
    browser.found["#tail-title"].update.assert_called_once_with("stdout.log")
    browser.follow_tail.assert_called_once_with(source, "a", "stdout.log")
    browser.run_worker.assert_called_once_with(
        browser.follow_tail.return_value,
        group="tail",
        exclusive=True,
        exit_on_error=False,
    )


def test_follow_tail_shows_text_binary_and_appends() -> None:
    browser = host(newline=True)
    log = browser.found["#tail"]
    seen: list[tuple[str, bool]] = []
    browser.write.side_effect = lambda shown, text: seen.append((text, browser.newline))
    source = daemon(
        ("state", {"name": "my log", "size": 4, "text": "one\n"}),
        ("append", {"text": "two\n"}),
        ("state", {"name": "my log", "size": 2048, "type": "image/png"}),
        ("append", {"size": 3}),
    )

    asyncio.run(FileBrowser.follow_tail(browser, source, "a", "my log"))

    assert source.routes == ["/runs/a/files/my%20log"]
    assert seen == [("one\n", False), ("two\n", False)]
    assert all(call.args[0] is log for call in browser.write.call_args_list)
    assert log.clear.call_count == 2
    log.write_line.assert_called_once_with(
        "Binary file (image/png, 2.0 kB), not shown."
    )


def test_follow_tail_says_when_the_file_is_gone() -> None:
    browser = host()
    log = browser.found["#tail"]

    asyncio.run(FileBrowser.follow_tail(browser, daemon(MISSING), "a", "x.log"))

    log.clear.assert_called_once_with()
    log.write_line.assert_called_once_with("x.log is gone.")


def test_write_holds_back_a_trailing_newline_until_more_text() -> None:
    browser = mock.Mock(newline=False)
    log = mock.Mock()

    FileBrowser.write(browser, log, "one\ntwo\n")
    assert browser.newline is True
    FileBrowser.write(browser, log, "thr")
    assert browser.newline is False
    FileBrowser.write(browser, log, "ee\n")

    assert [call.args[0] for call in log.write.call_args_list] == [
        "one\ntwo",
        "\nthr",
        "ee",
    ]
