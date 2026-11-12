import tomllib
from pathlib import Path

import pytest

from labnotes.cli import main


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def labnotes(project: Path, argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(project / ".labnotes.toml"), "experiments", *argv])
    return exit_info.value.code


def definition(path: Path) -> dict[str, object]:
    return tomllib.loads((path / "experiment.toml").read_text(encoding="utf-8"))


@pytest.fixture
def project(tmp_path: Path) -> Path:
    write(tmp_path / ".labnotes.toml", "")
    return tmp_path


def test_creates_an_experiment_from_flags(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = labnotes(
        project,
        ["new", "sanity-3", "--command", "uv run python run.py --out {run_dir}"]
        + ["--param", "model=opus", "--param", "model=sonnet"]
        + ["--param", "size=3", "--param", "langs=en,fr", "--repeats", "3"],
    )

    assert code == 0
    assert capsys.readouterr().out == (
        f"Created {project / 'sanity-3' / 'experiment.toml'}\n"
    )
    assert definition(project / "sanity-3") == {
        "command": "uv run python run.py --out {run_dir}",
        "repeats": 3,
        "continues": False,
        "params": {"model": ["opus", "sonnet"], "size": [3], "langs": ["en,fr"]},
    }


def test_copies_another_experiment_without_its_runs(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        project / "sanity-3/experiment.toml",
        '# The sanity check.\ncommand = "go {run_dir}"\nrepeats = 3\nmode = "adhoc"\n'
        '[params]\nmodel = ["opus", "sonnet"]\neffort = ["low"]\n',
    )
    write(project / "sanity-3/files/plan.md", "# Plan\n")
    write(project / "sanity-3/run.py", "print(1)\n")
    write(project / "sanity-3/runs/brave-fox/run.json", "{}")

    code = labnotes(
        project, ["new", "sanity-4", "--from", "sanity-3", "--param", "model=haiku"]
    )

    assert code == 0
    assert capsys.readouterr().out.startswith("Created ")
    copy = project / "sanity-4"
    assert definition(copy) == {
        "from": "sanity-3",
        "command": "go {run_dir}",
        "repeats": 3,
        "continues": False,
        "params": {"model": ["haiku"], "effort": ["low"]},
    }
    assert "# The sanity check." in (copy / "experiment.toml").read_text()
    assert (copy / "files/plan.md").read_text() == "# Plan\n"
    assert (copy / "run.py").read_text() == "print(1)\n"
    assert not (copy / "runs").exists()


def test_refuses_to_overwrite_an_experiment(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(project / "sanity-3/experiment.toml", 'command = "go"\n')
    write(project / "sanity-4/notes.md", "mine\n")

    code = labnotes(project, ["new", "sanity-4", "--from", "sanity-3"])

    assert code == 1
    assert "sanity-4 already exists" in capsys.readouterr().err
    assert sorted(p.name for p in (project / "sanity-4").iterdir()) == ["notes.md"]


def test_refuses_a_missing_source(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = labnotes(project, ["new", "sanity-4", "--from", "nope"])

    assert code == 1
    assert "No experiment.toml for nope" in capsys.readouterr().err
    assert not (project / "sanity-4").exists()


def test_new_flags_need_new(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write(project / "sanity-3/experiment.toml", 'command = "go"\n')

    code = labnotes(project, ["sanity-3", "--repeats", "2", "--format", "json"])

    assert code == 2
    assert "--repeats needs new" in capsys.readouterr().err
