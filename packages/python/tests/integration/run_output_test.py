import asyncio
from collections.abc import Callable
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Tab

from labnotes.tui.run_output import RunOutput


class Host(App[None]):
    def compose(self) -> ComposeResult:
        yield RunOutput(id="output")


def shown(output: RunOutput) -> list[str]:
    return [line.rstrip() for line in output.logs[output.current].lines]


def tabs(output: RunOutput) -> list[str]:
    return [tab.label_text for tab in output.query(Tab)]


def mounted(
    check: Callable[[RunOutput], None], size: tuple[int, int] = (80, 24)
) -> None:
    async def drive() -> None:
        app = Host()
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            check(app.query_one(RunOutput))

    asyncio.run(drive())


def append(path: Path, data: bytes) -> None:
    with path.open("ab") as file:
        file.write(data)


def test_starts_on_an_empty_stdout_tab() -> None:
    def check(output: RunOutput) -> None:
        assert output.current == "stdout"
        assert tabs(output) == ["stdout (0)", "stderr (0)"]
        assert shown(output) == []

    mounted(check)


def test_follows_nothing_before_a_run_writes_output(tmp_path: Path) -> None:
    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        assert shown(output) == []
        assert tabs(output) == ["stdout (0)", "stderr (0)"]

    mounted(check)


def test_follows_stderr_without_stdout(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("")
    (tmp_path / "stderr.log").write_text("oops\n")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        assert shown(output) == []
        assert tabs(output) == ["stdout (0)", "stderr (1)"]
        output.show("stderr")
        assert shown(output) == ["oops"]

    mounted(check)


def test_appends_only_new_bytes_on_each_follow(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("one\n")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        output.follow(tmp_path)
        append(tmp_path / "stdout.log", b"two\n")
        output.follow(tmp_path)
        assert shown(output) == ["one", "two"]
        assert output.logs["stdout"].read_to == 8

    mounted(check)


def test_decodes_characters_split_across_follows(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_bytes(b"caf\xc3")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        append(tmp_path / "stdout.log", b"\xa9 done\n")
        output.follow(tmp_path)
        assert shown(output) == ["café done"]

    mounted(check)


def test_shows_an_unfinished_line_and_continues_it(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("par")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        assert shown(output) == ["par"]
        assert output.logs["stdout"].mid_line
        append(tmp_path / "stdout.log", b"tial\nnext")
        output.follow(tmp_path)
        assert shown(output) == ["partial", "next"]
        append(tmp_path / "stdout.log", b"\n")
        output.follow(tmp_path)
        assert shown(output) == ["partial", "next"]
        assert not output.logs["stdout"].mid_line
        assert output.logs["stdout"].virtual_size.height == 2

    mounted(check)


def test_each_tab_shows_only_its_stream_with_live_counts(tmp_path: Path) -> None:
    stdout, stderr = tmp_path / "stdout.log", tmp_path / "stderr.log"
    stdout.write_text("next")
    stderr.write_text("oops\n")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        assert tabs(output) == ["stdout (0)", "stderr (1)"]
        append(stdout, b"\nmore\n")
        append(stderr, b"warn")
        output.follow(tmp_path)
        assert tabs(output) == ["stdout (2)", "stderr (1)"]
        append(stdout, b"end\n")
        append(stderr, b"ing\n")
        output.follow(tmp_path)
        assert tabs(output) == ["stdout (3)", "stderr (2)"]
        assert shown(output) == ["next", "more", "end"]
        output.show("stderr")
        assert shown(output) == ["oops", "warning"]

    mounted(check)


def test_renders_ansi_color(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_bytes(b"\x1b[31mred\x1b[0m plain\n\x1b[1mbo")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        append(tmp_path / "stdout.log", b"ld\x1b[0m\n")
        output.follow(tmp_path)
        assert shown(output) == ["\x1b[31mred\x1b[0m plain", "\x1b[1mbold\x1b[0m"]
        lines = [output.logs["stdout"].render_line(y) for y in range(2)]
        colors = {
            s.text.strip(): s.style.color.name if s.style and s.style.color else None
            for line in lines
            for s in line._segments
            if s.text.strip()
        }
        assert colors["red"] == "color(1)"
        assert colors["plain"] == colors["bold"]
        bold = [s.style for s in lines[1]._segments if s.text == "bold"]
        assert bold[0] is not None
        assert bold[0].bold

    mounted(check)


def test_drops_escapes_other_than_color(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_bytes(b"10%\r20%\x1b[2K done\n")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        assert (
            "".join(
                s.text for s in output.logs["stdout"].render_line(0)._segments
            ).strip()
            == "20% done"
        )

    mounted(check)


def test_long_lines_scroll_sideways_without_wrapping(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("word " * 12 + "\n")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        assert shown(output) == [("word " * 12).rstrip()]
        assert output.logs["stdout"].virtual_size.height == 1
        assert (
            output.logs["stdout"].virtual_size.width
            > output.logs["stdout"].scrollable_content_region.width
        )

    mounted(check, size=(30, 10))


def test_redraws_an_unfinished_long_line(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("word " * 12)

    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        append(tmp_path / "stdout.log", b"end\nnext\n")
        output.follow(tmp_path)
        lines = shown(output)
        assert lines == ["word " * 12 + "end", "next"]

    mounted(check, size=(30, 10))


def test_redraws_an_unfinished_line_written_before_the_size_is_known(
    tmp_path: Path,
) -> None:
    (tmp_path / "stdout.log").write_text("par")
    output = RunOutput()
    output.follow(tmp_path)
    append(tmp_path / "stdout.log", b"tial\n")
    output.follow(tmp_path)
    assert shown(output) == ["partial"]


def test_reset_starts_over_for_another_folder(tmp_path: Path) -> None:
    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    (tmp_path / "r1" / "stdout.log").write_bytes(b"cut \xe2\x82")
    (tmp_path / "r2" / "stdout.log").write_bytes(b"hi\n")
    (tmp_path / "r2" / "stderr.log").write_bytes(b"warn\n")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path / "r1")
        output.reset()
        assert shown(output) == []
        assert tabs(output) == ["stdout (0)", "stderr (0)"]
        assert not output.logs["stdout"].mid_line
        output.follow(tmp_path / "r2")
        assert shown(output) == ["hi"]
        assert tabs(output) == ["stdout (1)", "stderr (1)"]

    mounted(check)


def test_reset_forgets_an_unfinished_line(tmp_path: Path) -> None:
    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    (tmp_path / "r1" / "stdout.log").write_text("partial")
    (tmp_path / "r2" / "stdout.log").write_text("more\n")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path / "r1")
        output.reset()
        output.follow(tmp_path / "r2")
        assert shown(output) == ["more"]

    mounted(check)


def test_t_and_a_click_switch_between_the_stream_tabs(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("out\n")
    (tmp_path / "stderr.log").write_text("err\n")

    async def drive() -> None:
        app = Host()
        async with app.run_test() as pilot:
            output = app.query_one(RunOutput)
            output.follow(tmp_path)
            output.focus()
            await pilot.pause()
            assert app.focused is output.logs["stdout"]
            assert (output.logs["stdout"].display, output.logs["stderr"].display) == (
                True,
                False,
            )
            await pilot.press("t")
            await pilot.pause()
            assert (output.current, shown(output)) == ("stderr", ["err"])
            assert app.focused is output.logs["stderr"]
            assert not output.logs["stdout"].display
            await pilot.click("#stdout-tab")
            await pilot.pause()
            assert (output.current, shown(output)) == ("stdout", ["out"])
            assert output.logs["stdout"].display

    asyncio.run(drive())
