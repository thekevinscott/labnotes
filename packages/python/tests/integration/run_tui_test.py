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


def test_escape_backs_out_of_a_runs_output(terminal, tmp_path: Path) -> None:
    term = run_tui(terminal, tmp_path, 2)
    expect(term.get_by_text("2 runs to go")).to_be_visible()

    term.key_enter()
    expect(term.get_by_text("line 3")).to_be_visible()

    term.key_escape()
    expect(term.get_by_text("params")).to_be_visible()
    expect(term.get_by_text("line 3")).not_to_be_visible()

    term.key_ctrl_c()


def test_escape_backs_out_of_a_lone_adhoc_run(terminal, tmp_path: Path) -> None:
    term = run_tui(terminal, tmp_path, 1)
    expect(term.get_by_text("line 3")).to_be_visible()

    term.key_escape()
    expect(term.get_by_text("params")).to_be_visible()
    expect(term.get_by_text("line 3")).not_to_be_visible()

    term.key_ctrl_c()


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

    term.key_ctrl_c()


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

    term.key_ctrl_c()
