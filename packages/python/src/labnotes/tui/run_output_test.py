import asyncio
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import pytest
from textual.app import App, ComposeResult

from labnotes.tui.run_output import RunOutput


class Host(App[None]):
    def compose(self) -> ComposeResult:
        yield RunOutput(id="output")


def lines(output: RunOutput) -> list[str]:
    return [str(line) for line in output.lines]


def hosted(test: Callable[[RunOutput], Coroutine[Any, Any, None]]) -> None:
    async def drive() -> None:
        app = Host()
        async with app.run_test() as pilot:
            await pilot.pause()
            await test(app.query_one(RunOutput))

    asyncio.run(drive())


def test_takes_the_id_it_is_given() -> None:
    assert RunOutput(id="output").id == "output"


def test_follows_nothing_before_a_run_writes_output(tmp_path: Path) -> None:
    async def test(output: RunOutput) -> None:
        output.follow(tmp_path)
        assert lines(output) == []
        assert output.offsets == {"stdout": 0, "stderr": 0}

    hosted(test)


@pytest.mark.parametrize("stdout", [None, ""])
def test_follows_stderr_without_stdout(tmp_path: Path, stdout: str | None) -> None:
    if stdout is not None:
        (tmp_path / "stdout.log").write_text(stdout)
    (tmp_path / "stderr.log").write_text("oops\n")

    async def test(output: RunOutput) -> None:
        output.follow(tmp_path)
        assert lines(output) == ["oops", ""]
        assert output.offsets == {"stdout": 0, "stderr": 5}

    hosted(test)


def test_appends_only_new_bytes_on_each_follow(tmp_path: Path) -> None:
    async def test(output: RunOutput) -> None:
        (tmp_path / "stdout.log").write_text("one\n")
        output.follow(tmp_path)
        assert output.offsets == {"stdout": 4, "stderr": 0}
        output.follow(tmp_path)
        with (tmp_path / "stdout.log").open("a") as log:
            log.write("two\n")
        output.follow(tmp_path)
        assert lines(output) == ["one", "two", ""]
        assert output.offsets == {"stdout": 8, "stderr": 0}

    hosted(test)


def test_decodes_characters_split_across_follows(tmp_path: Path) -> None:
    async def test(output: RunOutput) -> None:
        (tmp_path / "stdout.log").write_bytes(b"caf\xc3")
        output.follow(tmp_path)
        assert lines(output) == ["caf"]
        with (tmp_path / "stdout.log").open("ab") as log:
            log.write(b"\xa9 done\n")
        output.follow(tmp_path)
        assert lines(output) == ["café done", ""]
        assert output.offsets == {"stdout": 11, "stderr": 0}

    hosted(test)


def test_continues_a_streams_own_unfinished_line(tmp_path: Path) -> None:
    async def test(output: RunOutput) -> None:
        (tmp_path / "stdout.log").write_text("par")
        output.follow(tmp_path)
        with (tmp_path / "stdout.log").open("a") as log:
            log.write("tial\n")
        output.follow(tmp_path)
        assert lines(output) == ["partial", ""]

    hosted(test)


def test_breaks_an_unfinished_line_before_the_other_stream(tmp_path: Path) -> None:
    async def test(output: RunOutput) -> None:
        (tmp_path / "stdout.log").write_text("next")
        (tmp_path / "stderr.log").write_text("oops\n")
        output.follow(tmp_path)
        assert lines(output) == ["next", "oops", ""]
        with (tmp_path / "stdout.log").open("a") as log:
            log.write("more\n")
        output.follow(tmp_path)
        assert lines(output) == ["next", "oops", "more", ""]
        with (tmp_path / "stderr.log").open("a") as log:
            log.write("warn")
        output.follow(tmp_path)
        with (tmp_path / "stdout.log").open("a") as log:
            log.write("end\n")
        output.follow(tmp_path)
        assert lines(output) == ["next", "oops", "more", "warn", "end", ""]

    hosted(test)


def test_reset_starts_over_for_another_folder(tmp_path: Path) -> None:
    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    (tmp_path / "r1" / "stdout.log").write_bytes(b"cut \xe2\x82")
    (tmp_path / "r2" / "stdout.log").write_bytes(b"hi\n")
    (tmp_path / "r2" / "stderr.log").write_bytes(b"warn\n")

    async def test(output: RunOutput) -> None:
        output.follow(tmp_path / "r1")
        output.reset()
        assert lines(output) == []
        assert output.offsets == {"stdout": 0, "stderr": 0}
        assert (output.last_stream, output.mid_line) == (None, False)
        output.follow(tmp_path / "r2")
        assert lines(output) == ["hi", "warn", ""]

    hosted(test)


def test_reset_forgets_an_unfinished_line(tmp_path: Path) -> None:
    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    (tmp_path / "r1" / "stdout.log").write_text("partial")
    (tmp_path / "r2" / "stderr.log").write_text("oops\n")

    async def test(output: RunOutput) -> None:
        output.follow(tmp_path / "r1")
        output.reset()
        output.follow(tmp_path / "r2")
        assert lines(output) == ["oops", ""]

    hosted(test)
