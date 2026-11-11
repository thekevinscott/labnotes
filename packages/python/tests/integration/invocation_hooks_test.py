import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest
from curtaincall import expect
from conftest import write

from labnotes.cli import main
from conftest import run_tui_command

MANY = '[params]\nm = ["a", "b"]\n'
COMMAND = """continues = false
command = "sh -c 'echo run $2 >> journal.txt' sh"
[params]
m = ["a", "b"]
"""


def labnotes(root: Path, argv: list[str]) -> int | str | None:
    if len(argv) >= 3 and argv[0] == "experiments" and argv[2] == "run":
        return run_tui_command(root, argv)
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(root / ".labnotes.toml"), *argv])
    return exit_info.value.code


def show_failure(terminal, root: Path, text: str) -> None:
    labnotes = Path(sys.executable).parent / "labnotes"
    term = terminal(
        f"{labnotes} -c {root / '.labnotes.toml'} experiments exp run",
        rows=30,
        cols=200,
    )
    expect(term.get_by_text(text)).to_be_visible(timeout=60)
    term.key_ctrl_c()
    term.wait(timeout=10)


def make_project(root: Path, shared: str = "", own: str = "") -> Path:
    write(
        root / ".labnotes.toml",
        f'[experiments]\npath = "{{experiment}}"\n[experiment]\n{shared}',
    )
    write(root / "exp" / "experiment.toml", own + COMMAND)
    return root


def journal(root: Path) -> list[str]:
    return (root / "journal.txt").read_text().splitlines()


def test_wraps_the_runs_in_the_projects_setup_and_teardown(tmp_path: Path) -> None:
    root = make_project(
        tmp_path,
        shared='setup = "echo up >> journal.txt"\n'
        'teardown = "echo down >> journal.txt"\n',
    )

    assert labnotes(root, ["experiments", "exp", "run"]) == 0

    assert journal(root) == ["up", "run a", "run b", "down"]


def test_prefers_the_experiments_setup_and_then_the_flags(tmp_path: Path) -> None:
    root = make_project(
        tmp_path,
        shared='setup = "echo shared >> journal.txt"\n'
        'teardown = "echo shared down >> journal.txt"\n',
        own='counts = "false"\nsetup = "echo own >> journal.txt"\n',
    )

    assert labnotes(root, ["experiments", "exp", "run"]) == 0
    assert (
        labnotes(
            root,
            [
                "experiments",
                "exp",
                "run",
                "--teardown",
                "echo flag down >> journal.txt",
            ],
        )
        == 0
    )

    assert journal(root) == [
        *["own", "run a", "run b", "shared down"],
        *["own", "run a", "run b", "flag down"],
    ]


def test_runs_nothing_but_still_tears_down_when_setup_fails(
    tmp_path: Path, terminal
) -> None:
    root = make_project(
        tmp_path,
        own='setup = "echo no db >&2; exit 4"\n'
        'teardown = "echo down >> journal.txt"\n',
    )

    show_failure(terminal, root, "setup command echo no db >&2; exit 4 exited 4: no db")

    assert journal(root) == ["down"]


def test_fails_the_invocation_when_teardown_fails(tmp_path: Path, terminal) -> None:
    root = make_project(tmp_path, own='teardown = "exit 5"\n')

    show_failure(terminal, root, "teardown command exit 5 exited 5")

    assert journal(root) == ["run a", "run b"]


def make_dir_project(root: Path, hooks: str, params: str = "") -> Path:
    write(root / ".labnotes.toml", '[experiments]\npath = "{experiment}"\n')
    write(
        root / "exp" / "experiment.toml",
        "continues = false\ncommand = \"sh -c 'echo run $1 $2 >> journal.txt' sh "
        '{run_dir} {invocation_dir}"\n' + hooks + params,
    )
    return root


def run_ids(root: Path) -> list[str]:
    runs = root / "exp" / "runs"
    return sorted(str(p.parent.relative_to(runs)) for p in runs.rglob("run.json"))


@pytest.mark.parametrize("params", ["", MANY])
def test_gives_each_run_its_own_folder_as_both_quoted_dirs(
    tmp_path: Path, params: str
) -> None:
    root = make_dir_project(tmp_path / "with spaces", "", params)

    assert labnotes(root, ["experiments", "exp", "run"]) == 0

    runs = run_ids(root)
    assert len(runs) == (2 if params else 1)
    folders = [str((root / "exp" / "runs" / run).resolve()) for run in runs]
    assert sorted(journal(root)) == sorted(f"run {f} {f}" for f in folders)


@pytest.mark.parametrize("params", ["", '[params]\nm = ["a", "b"]\n'])
@pytest.mark.parametrize("hook", ["setup", "teardown", "meta"])
@pytest.mark.parametrize("placeholder", ["{run_dir}", "{invocation_dir}"])
def test_refuses_a_folder_placeholder_in_any_hook_before_setup(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    params: str,
    hook: str,
    placeholder: str,
) -> None:
    hooks = {
        "setup": "echo up >> journal.txt",
        "teardown": "echo down >> journal.txt",
        "meta": "echo {}",
    }
    hooks[hook] = f"echo {hook} {placeholder} >> journal.txt"
    root = make_dir_project(
        tmp_path,
        "".join(f"{name} = '{command}'\n" for name, command in hooks.items()),
        params,
    )

    assert labnotes(root, ["experiments", "exp", "run"]) not in (0, None)

    assert (
        f"{hook} command echo {hook} {placeholder} >> journal.txt uses "
        f"{placeholder}; setup, teardown, and meta get no folder placeholders. "
        "Share values with set_state() and get_state()."
    ) in capsys.readouterr().err
    assert not (root / "journal.txt").exists()
    assert not (root / "exp" / "runs").exists()


SET_STATE = (
    "from labnotes import set_state\n"
    "set_state({'resource': 'one', 'kept': True})\n"
    "set_state({'resource': 'two'})\n"
)
GET_STATE = (
    "import json\nfrom pathlib import Path\nfrom labnotes import get_state\n"
    "Path('received.json').write_text(json.dumps(get_state()))\n"
)
READ_ONLY_STATE = """import json
import sys
from pathlib import Path
from labnotes import get_state, set_state

Path(sys.argv[1], 'received.json').write_text(json.dumps(get_state()))
try:
    set_state({'resource': 'changed by run'})
except RuntimeError:
    pass
else:
    raise AssertionError('Run state must be read-only')
with Path('journal.txt').open('a') as journal:
    journal.write('run\\n')
"""
NO_STATE = """from labnotes import get_state, set_state
for call in (get_state, lambda: set_state({'meta': True})):
    try:
        call()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Meta must not have state')
print('{}')
"""


def make_state_project(root: Path, params: str, setup_exit: int = 0) -> Path:
    write(root / "setup.py", SET_STATE + f"raise SystemExit({setup_exit})\n")
    write(root / "teardown.py", GET_STATE)
    write(root / "run.py", READ_ONLY_STATE)
    write(root / "meta.py", NO_STATE)
    write(root / ".labnotes.toml", '[experiments]\npath = "{experiment}"\n')
    write(
        root / "exp" / "experiment.toml",
        f'continues = false\ncommand = "{sys.executable} run.py {{run_dir}}"\n'
        f'meta = "{sys.executable} meta.py"\n'
        f'setup = "{sys.executable} setup.py"\n'
        f'teardown = "{sys.executable} teardown.py"\n' + params,
    )
    return root


@pytest.fixture(params=["LABNOTES_STATE", "LABNOTES_RUN_STATE"])
def outer_state(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[Path]:
    outer = tmp_path / "outer.json"
    outer.write_text('{"outer": true}')
    with mock.patch.dict(os.environ, {request.param: str(outer)}):
        yield outer


@pytest.mark.parametrize("params", ["", MANY])
def test_runs_read_setup_state_without_changing_teardown_or_outer_state(
    tmp_path: Path, outer_state: Path, params: str
) -> None:
    root = make_state_project(tmp_path / "project", params)

    assert labnotes(root, ["experiments", "exp", "run"]) == 0

    expected = {"resource": "two", "kept": True}
    assert json.loads((root / "received.json").read_text()) == expected
    runs = list((root / "exp" / "runs").rglob("run.json"))
    assert len(runs) == (2 if params else 1)
    for run in runs:
        assert json.loads(run.with_name("received.json").read_text()) == expected
        assert "resource" not in run.read_text()
    assert journal(root) == ["run"] * len(runs)
    assert outer_state.read_text() == '{"outer": true}'


def test_gives_teardown_the_state_set_before_setup_failed(
    tmp_path: Path, terminal
) -> None:
    root = make_state_project(tmp_path, MANY, setup_exit=3)

    show_failure(terminal, root, "exited 3")

    assert json.loads((root / "received.json").read_text()) == {
        "resource": "two",
        "kept": True,
    }
    assert not (root / "journal.txt").exists()
