from pathlib import Path

from labnotes.models import LabnotesConfig
from labnotes.runner.hook_folder import hook_folder


def config(root: Path, experiments: str) -> LabnotesConfig:
    return LabnotesConfig(root / ".labnotes.toml", root, experiments, "files/", "runs")


def test_puts_hook_logs_under_the_experiments_labnotes_folder(tmp_path: Path) -> None:
    folder = hook_folder(
        config(tmp_path, "studies/{experiment}"), "alpha", "setup", "s1"
    )

    assert folder == tmp_path / "studies/alpha/.labnotes/logs/setup/s1"


def test_uses_the_root_when_the_root_is_the_experiment(tmp_path: Path) -> None:
    folder = hook_folder(config(tmp_path, ""), "alpha", "teardown", "s1")

    assert folder == tmp_path / ".labnotes/logs/teardown/s1"
