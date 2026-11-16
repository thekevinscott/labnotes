import asyncio
import sys
from pathlib import Path

from click.testing import CliRunner

from labnotes.cli import main
from labnotes.models import ExperimentConfig
from labnotes.read_config import read_config
from labnotes.runner.prepare_experiment import prepare_experiment
from labnotes.tables.open_experiment_tables import open_experiment_tables


def test_relative_override_reads_the_file_in_the_project_folder(tmp_path: Path) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text('command = "false"\n')
    (tmp_path / "alt").mkdir()
    command = f"{sys.executable} -c 'print(317)'"
    (tmp_path / "alt/experiment.toml").write_text(
        f'command = "{command}"\ncontinues = false\n'
    )

    config = read_config(tmp_path / ".labnotes.toml")

    async def prepare() -> ExperimentConfig:
        experiment, _ = await prepare_experiment(
            config,
            "exp",
            Path("alt/experiment.toml"),
            None,
            tables=open_experiment_tables(config, "exp"),
        )
        return experiment

    experiment = asyncio.run(prepare())

    assert experiment.command == command


def test_missing_override_is_a_usage_error(tmp_path: Path) -> None:
    (tmp_path / ".labnotes.toml").write_text("")

    result = CliRunner().invoke(
        main,
        [
            "-c",
            str(tmp_path / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
            "-e",
            str(tmp_path / "missing.toml"),
        ],
    )

    assert result.exit_code == 2
    assert "does not exist" in result.output
    assert "Traceback" not in result.output
