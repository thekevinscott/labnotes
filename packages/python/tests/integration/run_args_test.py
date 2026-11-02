import json
import sys
from pathlib import Path

import pytest

from labnotes.cli import main

SCRIPT = "import sys\nprint(*sys.argv[1:])\n"


def make_project(root: Path, command: str = "--out x", config: str = "") -> Path:
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text(config)
    (root / "script.py").write_text(SCRIPT)
    (root / "exp" / "experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} script.py {command}"\n[params]\nm = ["a", "b"]\n'
    )
    return root


def labnotes(project: Path, argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(project / ".labnotes.toml"), "experiments", "exp", *argv])
    return exit_info.value.code


def only_run(project: Path) -> Path:
    [folder] = [path.parent for path in (project / "exp" / "runs").glob("**/run.json")]
    return folder


def test_appends_and_records_the_args(tmp_path: Path) -> None:
    project = make_project(tmp_path)

    assert labnotes(project, ["run", "--m=a", "--", "--auth", "api key"]) == 0

    folder = only_run(project)
    run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    assert run["args"] == ["--auth", "api key"]
    assert run["command"].endswith("--out x --m a --auth 'api key'")
    assert (folder / "stdout.log").read_text() == "--out x --m a --auth api key\n"


@pytest.mark.parametrize(
    ("command", "args", "received"),
    [
        ("--memory 8g --out x", ["--memory", "24g"], "--memory 24g --out x"),
        ("--memory 8g --out x", ["--memory=24g"], "--memory 24g --out x"),
        ("--memory=8g --out x", ["--memory", "24g"], "--memory=24g --out x"),
        ("--memory=8g --out x", ["--memory=24g"], "--memory=24g --out x"),
    ],
)
def test_args_override_a_flag_in_the_command(
    tmp_path: Path, command: str, args: list[str], received: str
) -> None:
    project = make_project(tmp_path, command)

    assert labnotes(project, ["run", "--m=a", "--", *args, "--auth", "api"]) == 0

    folder = only_run(project)
    run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    assert run["args"] == [*args, "--auth", "api"]
    assert run["command"].endswith(f"{received} --m a --auth api")
    assert (folder / "stdout.log").read_text() == f"{received} --m a --auth api\n"


def test_args_override_a_command_from_the_labnotes_toml(tmp_path: Path) -> None:
    (tmp_path / "script.py").write_text(SCRIPT)
    (tmp_path / ".labnotes.toml").write_text(
        "[experiment]\n"
        f'continues = false\ncommand = "{sys.executable} script.py --memory 8g --out x"\n'
    )

    with pytest.raises(SystemExit) as exit_info:
        main(
            ["-c", str(tmp_path / ".labnotes.toml"), "experiments", tmp_path.name]
            + ["run", "--", "--memory", "24g"]
        )
    assert exit_info.value.code == 0

    [log] = (tmp_path / "runs").glob("**/stdout.log")
    assert log.read_text() == "--memory 24g --out x\n"


@pytest.mark.parametrize(
    ("command", "args", "error"),
    [
        ("--out x", ["--m", "b"], "--m is a param. Pick it with --m=VALUE."),
        (
            "--out x --out y",
            ["--out=z"],
            "--out is in the command more than once, so -- can't override it.",
        ),
        ("--out x", ["--out=y", "--out=z"], "--out is in -- ARGS more than once."),
    ],
)
def test_refuses_args_that_override_the_design_or_are_ambiguous(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: str,
    args: list[str],
    error: str,
) -> None:
    project = make_project(tmp_path, command)

    assert labnotes(project, ["run", "--", *args]) == 1

    assert f"Error: {error}" in capsys.readouterr().err
    assert not (project / "exp" / "runs").exists()
