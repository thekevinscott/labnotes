import re
import json
import shlex
import sys
import time
from collections.abc import Iterator
from pathlib import Path

from curtaincall import Terminal, expect
import psutil
import pytest


@pytest.fixture(autouse=True)
def cleanup_daemons(tmp_path: Path) -> Iterator[None]:
    yield
    config = str(tmp_path / ".labnotes.toml")
    owners = [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (process.info["cmdline"] or [])
        and "daemon" in (process.info["cmdline"] or [])
    ]
    for process in owners:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(owners, timeout=15)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass


COMMAND = (
    f"{shlex.quote(sys.executable)} -c "
    "\"import time\nfor i in range(100): print('line', i, flush=True); time.sleep(0.2)\""
)


def run_tui(
    terminal, tmp_path: Path, repeats: int, command: str = COMMAND, extra: str = ""
) -> Terminal:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp" / "experiment.toml").write_text(
        f"continues = false\ncommand = '''{command}'''\nrepeats = {repeats}\n{extra}"
    )
    labnotes = Path(sys.executable).parent / "labnotes"
    return terminal(
        f"{labnotes} -c {tmp_path / '.labnotes.toml'} experiments exp run",
        rows=30,
        cols=120,
    )


def stop(term: Terminal) -> None:
    term.key_ctrl_c()
    expect(term.get_by_text("leave running")).to_be_visible()
    term.write("s")


def test_escape_backs_out_of_a_runs_output(terminal, tmp_path: Path) -> None:
    term = run_tui(terminal, tmp_path, 2)
    expect(term.get_by_text("1 at a time")).to_be_visible()

    term.key_enter()
    expect(term.get_by_text("line 3")).to_be_visible()

    term.key_escape()
    expect(term.get_by_text("params")).to_be_visible()
    expect(term.get_by_text("line 3")).not_to_be_visible()

    stop(term)


def test_escape_backs_out_of_a_lone_run(terminal, tmp_path: Path) -> None:
    term = run_tui(terminal, tmp_path, 1)
    expect(term.get_by_text("line 3")).to_be_visible()

    term.key_escape()
    expect(term.get_by_text("params")).to_be_visible()
    expect(term.get_by_text("line 3")).not_to_be_visible()

    stop(term)


def test_coming_back_to_a_run_shows_its_output_so_far_and_keeps_following(
    terminal, tmp_path: Path
) -> None:
    term = run_tui(terminal, tmp_path, 2)
    expect(term.get_by_text("params")).to_be_visible()
    time.sleep(1)

    term.key_enter()
    expect(term.get_by_text("line 0")).to_be_visible()
    expect(term.get_by_text("line 3")).to_be_visible()

    term.key_escape()
    expect(term.get_by_text("line 3")).not_to_be_visible()
    time.sleep(1)

    term.key_enter()
    expect(term.get_by_text("line 0")).to_be_visible()
    expect(term.get_by_text("line 15")).to_be_visible()

    stop(term)


def test_shows_a_running_runs_memory_and_size(terminal, tmp_path: Path) -> None:
    term = run_tui(terminal, tmp_path, 2)
    expect(term.get_by_text("memory")).to_be_visible()
    expect(
        term.get_by_text(re.compile(r"\d+\.\d MB +\d+(\.\d)? (kB|MB|bytes)"))
    ).to_be_visible()

    stop(term)


def test_live_table_shows_columns_status_time_badge_and_footer(
    terminal, tmp_path: Path
) -> None:
    term = run_tui(terminal, tmp_path, 2)
    for label in ("run", "params", "status", "time", "memory", "size"):
        expect(term.get_by_text(label)).to_be_visible()
    expect(term.get_by_text("1 at a time")).to_be_visible()
    expect(term.get_by_text(re.compile(r"[|/\\-] +\d+s"))).to_be_visible()
    expect(term.get_by_text("○")).to_be_visible()
    for key in ("Stop run", "Filter", "More at once", "Fewer at once"):
        expect(term.get_by_text(key)).to_be_visible()
    term.key_enter()
    expect(term.get_by_text("Back")).to_be_visible()
    term.key_escape()
    expect(term.get_by_text("1 runs")).not_to_be_visible()
    stop(term)


def test_filter_and_concurrency_keys(terminal, tmp_path: Path) -> None:
    term = run_tui(terminal, tmp_path, 2)
    expect(term.get_by_text("1 at a time")).to_be_visible()
    term.write("+")
    expect(term.get_by_text("2 at a time")).to_be_visible()
    term.write("-")
    expect(term.get_by_text("1 at a time")).to_be_visible()
    term.write("/")
    expect(term.get_by_text("Filter params")).to_be_visible()
    term.write("nomatch")
    expect(term.get_by_text("nomatch")).to_be_visible()
    term.key_enter()
    term.key_escape()
    expect(term.get_by_text("Filter params")).not_to_be_visible()
    stop(term)


def test_x_stops_selected_run(terminal, tmp_path: Path) -> None:
    term = run_tui(terminal, tmp_path, 2)
    expect(term.get_by_text(re.compile(r"[|/\\-] +\d+s"))).to_be_visible()
    term.write("x")
    expect(term.get_by_text(re.compile(r"✗|killing|stopping"))).to_be_visible()
    stop(term)


def test_finish_up_finishes_current_run_without_starting_queued_run(
    terminal, tmp_path: Path
) -> None:
    command = f"{shlex.quote(sys.executable)} -c 'import time; time.sleep(2)'"
    term = run_tui(terminal, tmp_path, 2, command)
    expect(term.get_by_text(re.compile(r"[|/\\-] +\d+s"))).to_be_visible()
    expect(term.get_by_text("Finish up")).to_be_visible()
    term.write("d")
    expect(term.get_by_text("Finishing up")).not_to_be_visible()
    expect(term.get_by_text("Draining")).not_to_be_visible()
    term.write("f")
    expect(term.get_by_text("Finishing up")).to_be_visible()
    assert term.is_alive
    expect(term.get_by_text("1 passed, 0 failed")).to_be_visible(timeout=15)
    records = [
        json.loads(path.read_text()) for path in tmp_path.glob("exp/runs/*/run.json")
    ]
    assert len(records) == 1
    assert records[0]["exit_code"] == 0
    assert records[0]["ended_by"] is None
    term.key_ctrl_c()
    term.wait()


def test_finish_up_from_output_view_keeps_status_line_on_return(
    terminal, tmp_path: Path
) -> None:
    command = f"{shlex.quote(sys.executable)} -c 'import time; time.sleep(8)'"
    term = run_tui(terminal, tmp_path, 2, command)
    expect(term.get_by_text(re.compile(r"[|/\\-] +\d+s"))).to_be_visible()
    term.key_enter()
    expect(term.get_by_text("Back")).to_be_visible()
    term.write("f")
    expect(term.get_by_text("Finishing up")).to_be_visible()
    term.key_escape()
    expect(term.get_by_text("Back")).not_to_be_visible()
    expect(
        term.get_by_text(
            "Finishing up. Queued runs won't start; running cells will finish."
        )
    ).to_be_visible()
    expect(term.get_by_text("–")).to_be_visible()
    term.key_ctrl_c()
    term.wait()


def test_retry_wait_and_end_summary(terminal, tmp_path: Path) -> None:
    command = f"{shlex.quote(sys.executable)} -c 'import sys; sys.exit(75)'"
    term = run_tui(terminal, tmp_path, 2, command, "retries = 1\n")
    expect(term.get_by_text("retry in")).to_be_visible(timeout=15)
    expect(term.get_by_text("✗")).to_be_visible()
    term.key_ctrl_c()
    expect(term.get_by_text("waiting to retry. Stop (s)")).to_be_visible()
    term.write("s")
    term.wait()


def test_end_summary_shows_passed_and_failed(terminal, tmp_path: Path) -> None:
    command = f"{shlex.quote(sys.executable)} -c 'print(\"done\")'"
    term = run_tui(terminal, tmp_path, 2, command, "retries = 0\n")
    expect(term.get_by_text("2 passed, 0 failed")).to_be_visible(timeout=15)
    expect(term.get_by_text("✓")).to_be_visible()
    term.key_ctrl_c()
    term.wait()


def test_ctrl_c_prompt_can_cancel_then_stop(terminal, tmp_path: Path) -> None:
    term = run_tui(terminal, tmp_path, 2)
    expect(term.get_by_text("1 at a time")).to_be_visible()
    term.key_ctrl_c()
    expect(term.get_by_text("leave running")).to_be_visible()
    expect(term.get_by_text("Stop (s)")).to_be_visible()
    term.key_escape()
    expect(term.get_by_text("leave running")).not_to_be_visible()
    term.key_ctrl_c()
    expect(term.get_by_text("leave running")).to_be_visible()
    term.write("s")
    term.wait()
    records = [
        json.loads(path.read_text()) for path in tmp_path.glob("exp/runs/*/run.json")
    ]
    assert records
    assert any(record["ended_by"] == "stop" for record in records)
