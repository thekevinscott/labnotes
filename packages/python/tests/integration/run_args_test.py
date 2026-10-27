import json
import sys
from pathlib import Path

import pytest

from labnotes.cli import main

SCRIPT = "import sys\nprint(*sys.argv[1:])\n"


def make_project(root: Path) -> Path:
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(SCRIPT)
    (root / "exp" / "experiment.toml").write_text(
        f'command = "{sys.executable} script.py --out x"\n[params]\nm = ["a", "b"]\n'
    )
    return root


def labnotes(project: Path, argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(project / ".labnotes.toml"), "experiments", "exp", *argv])
    return exit_info.value.code


def test_appends_and_records_the_args(tmp_path: Path) -> None:
    project = make_project(tmp_path)

    assert labnotes(project, ["run", "--m=a", "--", "--auth", "api key"]) == 0

    [folder] = [path.parent for path in (project / "exp" / "runs").glob("**/run.json")]
    run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    assert run["args"] == ["--auth", "api key"]
    assert run["command"].endswith("--out x --m a --auth 'api key'")
    assert (folder / "stdout.log").read_text() == "--out x --m a --auth api key\n"


@pytest.mark.parametrize(
    ("args", "error"),
    [
        (["--m", "b"], "--m is a param. Pick it with --m=VALUE."),
        (["--out=y"], "--out is already in the command."),
    ],
)
def test_refuses_args_that_override_the_design(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], args: list[str], error: str
) -> None:
    project = make_project(tmp_path)

    assert labnotes(project, ["run", "--", *args]) == 1

    assert f"Error: {error}" in capsys.readouterr().err
    assert not (project / "exp" / "runs").exists()
