import asyncio
from collections.abc import Callable
from pathlib import Path

from textual.app import App, ComposeResult

from labnotes.tui.run_output import RunOutput


class Host(App[None]):
    def compose(self) -> ComposeResult:
        yield RunOutput(id="output")


def shown(output: RunOutput) -> list[str]:
    return [line.text.rstrip() for line in output.lines]


def mounted(check: Callable[[RunOutput], None]) -> None:
    async def drive() -> None:
        app = Host()
        async with app.run_test() as pilot:
            await pilot.pause()
            check(app.query_one(RunOutput))

    asyncio.run(drive())


def append(path: Path, data: bytes) -> None:
    with path.open("ab") as file:
        file.write(data)


def test_starts_empty() -> None:
    output = RunOutput(id="output")
    assert output.id == "output"
    assert output.offsets == {"stdout": 0, "stderr": 0}
    assert (output.last_stream, output.mid_line) == (None, False)


def test_follows_nothing_before_a_run_writes_output(tmp_path: Path) -> None:
    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        assert shown(output) == []
        assert output.offsets == {"stdout": 0, "stderr": 0}

    mounted(check)


def test_follows_stderr_without_stdout(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("")
    (tmp_path / "stderr.log").write_text("oops\n")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        assert shown(output) == ["oops"]
        assert output.offsets == {"stdout": 0, "stderr": 5}

    mounted(check)


def test_appends_only_new_bytes_on_each_follow(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_text("one\n")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        output.follow(tmp_path)
        append(tmp_path / "stdout.log", b"two\n")
        output.follow(tmp_path)
        assert shown(output) == ["one", "two"]
        assert output.offsets == {"stdout": 8, "stderr": 0}

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
        assert output.mid_line
        append(tmp_path / "stdout.log", b"tial\nnext")
        output.follow(tmp_path)
        assert shown(output) == ["partial", "next"]
        append(tmp_path / "stdout.log", b"\n")
        output.follow(tmp_path)
        assert shown(output) == ["partial", "next"]
        assert not output.mid_line
        assert output.virtual_size.height == 2

    mounted(check)


def test_breaks_an_unfinished_line_before_the_other_stream(tmp_path: Path) -> None:
    stdout, stderr = tmp_path / "stdout.log", tmp_path / "stderr.log"
    stdout.write_text("next")
    stderr.write_text("oops\n")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        assert (output.last_stream, output.mid_line) == ("stderr", False)
        append(stdout, b"more\n")
        output.follow(tmp_path)
        append(stderr, b"warn")
        output.follow(tmp_path)
        assert (output.last_stream, output.mid_line) == ("stderr", True)
        append(stdout, b"end\n")
        output.follow(tmp_path)
        assert shown(output) == ["next", "oops", "more", "warn", "end"]

    mounted(check)


def test_renders_ansi_color(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_bytes(b"\x1b[31mred\x1b[0m plain\n\x1b[1mbo")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        append(tmp_path / "stdout.log", b"ld\x1b[0m\n")
        output.follow(tmp_path)
        assert shown(output) == ["red plain", "bold"]
        colors = {
            s.text.strip(): s.style.color.name if s.style and s.style.color else None
            for line in output.lines
            for s in line
            if s.text.strip()
        }
        assert colors == {"red": "color(1)", "plain": None, "bold": None}
        bold = [s.style for s in output.lines[1] if s.text == "bold"]
        assert bold[0] is not None
        assert bold[0].bold

    mounted(check)


def test_drops_escapes_other_than_color(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_bytes(b"10%\r20%\x1b[2K done\n")

    def check(output: RunOutput) -> None:
        output.follow(tmp_path)
        assert shown(output) == ["20% done"]

    mounted(check)


def test_redraws_an_unfinished_line_written_before_the_size_is_known(
    tmp_path: Path,
) -> None:
    (tmp_path / "stdout.log").write_text("par")
    output = RunOutput()
    output.follow(tmp_path)
    append(tmp_path / "stdout.log", b"tial\n")
    output.follow(tmp_path)
    assert [str(render.content) for render in output._deferred_renders] == ["partial"]


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
        assert output.offsets == {"stdout": 0, "stderr": 0}
        assert (output.last_stream, output.mid_line) == (None, False)
        output.follow(tmp_path / "r2")
        assert shown(output) == ["hi", "warn"]

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
