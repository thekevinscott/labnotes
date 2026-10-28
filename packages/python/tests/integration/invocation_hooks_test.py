import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest
from conftest import write

from labnotes.cli import main

MANY = '[params]\nm = ["a", "b"]\n'
COMMAND = """command = "sh -c 'echo run $2 >> journal.txt' sh"
[params]
m = ["a", "b"]
"""


def labnotes(root: Path, argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(root / ".labnotes.toml"), *argv])
    return exit_info.value.code


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
        own='setup = "echo own >> journal.txt"\n',
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
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(
        tmp_path,
        own='setup = "echo no db >&2; exit 4"\n'
        'teardown = "echo down >> journal.txt"\n',
    )

    assert labnotes(root, ["experiments", "exp", "run"]) not in (0, None)

    assert "setup command echo no db >&2; exit 4 exited 4: no db" in (
        capsys.readouterr().err
    )
    assert journal(root) == ["down"]


def test_fails_the_invocation_when_teardown_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(tmp_path, own='teardown = "exit 5"\n')

    assert labnotes(root, ["experiments", "exp", "run"]) not in (0, None)

    assert "teardown command exit 5 exited 5" in capsys.readouterr().err
    assert journal(root) == ["run a", "run b"]


def make_dir_project(root: Path, hooks: str, params: str = "") -> Path:
    write(root / ".labnotes.toml", '[experiments]\npath = "{experiment}"\n')
    write(
        root / "exp" / "experiment.toml",
        "command = \"sh -c 'echo run $1 $2 >> journal.txt' sh "
        '{run_dir} {invocation_dir}"\n' + hooks + params,
    )
    return root


def run_ids(root: Path) -> list[str]:
    runs = root / "exp" / "runs"
    return sorted(str(p.parent.relative_to(runs)) for p in runs.rglob("run.json"))


@pytest.mark.parametrize("mode", ["adhoc", "matrix"])
def test_gives_a_lone_run_and_its_hooks_the_same_quoted_dirs(
    tmp_path: Path, mode: str
) -> None:
    root = make_dir_project(
        tmp_path / "with spaces",
        'setup = "test -d {invocation_dir} && echo remote > '
        '{invocation_dir}/machine.txt && echo up {invocation_dir} >> journal.txt"\n'
        'teardown = "cat {invocation_dir}/machine.txt >> journal.txt && '
        'echo down {invocation_dir} >> journal.txt"\n'
        f'mode = "{mode}"\n',
    )

    assert labnotes(root, ["experiments", "exp", "run"]) == 0

    [run] = run_ids(root)
    folder = str((root / "exp" / "runs" / run).resolve())
    assert journal(root) == [
        f"up {folder}",
        f"run {folder} {folder}",
        "remote",
        f"down {folder}",
    ]


def test_uses_the_invocation_folder_shared_by_adhoc_runs(tmp_path: Path) -> None:
    root = make_dir_project(
        tmp_path,
        'setup = "test -d {invocation_dir} && echo remote > '
        '{invocation_dir}/machine.txt && echo up {invocation_dir} >> journal.txt"\n'
        'teardown = "cat {invocation_dir}/machine.txt >> journal.txt && '
        'echo down {invocation_dir} >> journal.txt"\n',
        '[params]\nm = ["a", "b"]\n',
    )

    assert labnotes(root, ["experiments", "exp", "run"]) == 0

    runs = run_ids(root)
    group = runs[0].split("/")[0]
    assert [run.split("/")[0] for run in runs] == [group, group]
    group_dir = str((root / "exp" / "runs" / group).resolve())
    lines = journal(root)
    assert (lines[0], lines[-2:]) == (
        f"up {group_dir}",
        ["remote", f"down {group_dir}"],
    )
    assert sorted(lines[1:-2]) == [
        f"run {(root / 'exp' / 'runs' / run).resolve()} {group_dir}" for run in runs
    ]


@pytest.mark.parametrize("params", ["", '[params]\nm = ["a", "b"]\n'])
def test_refuses_run_dir_in_setup_for_any_run_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], params: str
) -> None:
    root = make_dir_project(
        tmp_path, 'setup = "echo up {run_dir} >> journal.txt"\n', params
    )

    assert labnotes(root, ["experiments", "exp", "run"]) not in (0, None)

    assert (
        "setup command echo up {run_dir} >> journal.txt uses {run_dir}; "
        "use {invocation_dir} instead." in capsys.readouterr().err
    )
    assert not (root / "journal.txt").exists()


def test_refuses_invocation_dir_in_matrix_setup_with_many_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(
        tmp_path,
        own='mode = "matrix"\nsetup = "echo up {invocation_dir} >> journal.txt"\n',
    )

    assert labnotes(root, ["experiments", "exp", "run"]) not in (0, None)

    assert (
        "setup command echo up {invocation_dir} >> journal.txt uses {invocation_dir}"
        in (capsys.readouterr().err)
    )
    assert not (root / "journal.txt").exists()


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


def make_state_project(root: Path, mode: str, params: str, setup_exit: int = 0) -> Path:
    write(root / "setup.py", SET_STATE + f"raise SystemExit({setup_exit})\n")
    write(root / "teardown.py", GET_STATE)
    write(root / "run.py", READ_ONLY_STATE)
    write(root / "meta.py", NO_STATE)
    write(root / ".labnotes.toml", '[experiments]\npath = "{experiment}"\n')
    write(
        root / "exp" / "experiment.toml",
        f'command = "{sys.executable} run.py {{run_dir}}"\n'
        f'meta = "{sys.executable} meta.py"\n'
        f'mode = "{mode}"\n'
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


@pytest.mark.parametrize(
    ("mode", "params"),
    [("adhoc", ""), ("adhoc", MANY), ("matrix", ""), ("matrix", MANY)],
)
def test_runs_read_setup_state_without_changing_teardown_or_outer_state(
    tmp_path: Path, outer_state: Path, mode: str, params: str
) -> None:
    root = make_state_project(tmp_path / "project", mode, params)

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


def test_gives_teardown_the_state_set_before_setup_failed(tmp_path: Path) -> None:
    root = make_state_project(tmp_path, "matrix", MANY, setup_exit=3)

    assert labnotes(root, ["experiments", "exp", "run"]) not in (0, None)

    assert json.loads((root / "received.json").read_text()) == {
        "resource": "two",
        "kept": True,
    }
    assert not (root / "journal.txt").exists()
