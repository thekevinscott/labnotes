import re
import shlex
import sys
import time
from pathlib import Path

from curtaincall import Terminal, expect

COMMAND = (
    f"{shlex.quote(sys.executable)} -c "
    "\"import time\nfor i in range(100): print('line', i, flush=True); time.sleep(0.2)\""
)


def run_tui(terminal, tmp_path: Path, repeats: int) -> Terminal:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp" / "experiment.toml").write_text(
        f"command = '''{COMMAND}'''\nrepeats = {repeats}\n"
    )
    labnotes = Path(sys.executable).parent / "labnotes"
    return terminal(
        f"{labnotes} -c {tmp_path / '.labnotes.toml'} experiments exp run",
        rows=30,
        cols=120,
    )


def stop(term: Terminal) -> None:
    term.key_ctrl_c()
    expect(term.get_by_text("still going")).to_be_visible()
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


def test_escape_backs_out_of_a_lone_adhoc_run(terminal, tmp_path: Path) -> None:
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


def test_lists_adhoc_runs_by_the_params_that_vary(terminal, tmp_path: Path) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp" / "experiment.toml").write_text(
        f"command = '''{COMMAND}'''\nmode = 'adhoc'\n"
        "[params]\nproblem = ['../data/0580', '../data/2002']\n"
    )
    labnotes = Path(sys.executable).parent / "labnotes"
    term = terminal(
        f"{labnotes} -c {tmp_path / '.labnotes.toml'} experiments exp run",
        rows=30,
        cols=120,
    )

    expect(term.get_by_text(re.compile(r"0580-[0-9a-f]{4}"))).to_be_visible()
    expect(term.get_by_text(re.compile(r"2002-[0-9a-f]{4}"))).to_be_visible()

    stop(term)


def test_moving_a_pending_run_changes_the_order_runs_start(
    terminal, tmp_path: Path
) -> None:
    started = tmp_path / "started.txt"
    script = (
        "import sys, time\n"
        f"open({str(started)!r}, 'a').write(sys.argv[2] + '\\n')\n"
        "time.sleep(3 if sys.argv[2] == 'a' else 0.1)"
    )
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp" / "experiment.toml").write_text(
        f"command = '''{shlex.quote(sys.executable)} -c {shlex.quote(script)}'''\n"
        "[params]\nm = ['a', 'b', 'c']\n"
    )
    labnotes = Path(sys.executable).parent / "labnotes"
    term = terminal(
        f"{labnotes} -c {tmp_path / '.labnotes.toml'} experiments exp run",
        rows=30,
        cols=120,
    )
    expect(term.get_by_text("1 at a time")).to_be_visible()

    term.write("j")
    term.write("m")
    expect(term.get_by_text("Moving")).to_be_visible()
    term.write("j")
    term.key_enter()
    expect(term.get_by_text("moved to 2 of 2 in the queue")).to_be_visible()
    expect(term.get_by_text("3 passed")).to_be_visible(timeout=15)

    assert started.read_text().split() == ["a", "c", "b"]

    term.key_ctrl_c()
