from pathlib import Path

from labnotes.copy_experiment import copy_experiment


def write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def files(folder: Path) -> list[str]:
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())


def test_copies_everything_but_the_runs_folder(tmp_path: Path) -> None:
    source = tmp_path / "a"
    write(source / "experiment.toml", "x")
    write(source / "files/plan.md", "plan")
    write(source / "runs/one/run.json")
    write(source / "deep/runs/kept.md")

    copy_experiment(source, tmp_path / "b", source / "runs")

    assert files(tmp_path / "b") == [
        "deep/runs/kept.md",
        "experiment.toml",
        "files/plan.md",
    ]
    assert (tmp_path / "b/files/plan.md").read_text() == "plan"


def test_skips_run_folders_that_sit_in_the_experiment_folder(tmp_path: Path) -> None:
    source = tmp_path / "a"
    write(source / "experiment.toml")
    write(source / "one/run.json")
    write(source / "files/plan.md")
    write(source / "files/nested/run.json")

    copy_experiment(source, tmp_path / "b", source)

    assert files(tmp_path / "b") == [
        "experiment.toml",
        "files/nested/run.json",
        "files/plan.md",
    ]


def test_copies_it_all_when_runs_live_elsewhere(tmp_path: Path) -> None:
    source = tmp_path / "notes/a"
    write(source / "experiment.toml")
    write(source / "runs/kept.md")

    copy_experiment(source, tmp_path / "notes/b", tmp_path / "data/a")

    assert files(tmp_path / "notes/b") == ["experiment.toml", "runs/kept.md"]


def test_keeps_symlinks_as_links(tmp_path: Path) -> None:
    source = tmp_path / "a"
    write(source / "experiment.toml")
    (source / "data").symlink_to(tmp_path / "elsewhere")

    copy_experiment(source, tmp_path / "b", source / "runs")

    assert (tmp_path / "b/data").readlink() == tmp_path / "elsewhere"
