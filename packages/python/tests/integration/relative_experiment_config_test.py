import asyncio
import sys
from pathlib import Path

from labnotes.read_config import read_config
from labnotes.runner.prepare_experiment import prepare_experiment


def test_relative_override_reads_the_file_in_the_project_folder(tmp_path: Path) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text('command = "false"\n')
    (tmp_path / "alt").mkdir()
    command = f"{sys.executable} -c 'print(317)'"
    (tmp_path / "alt/experiment.toml").write_text(
        f'command = "{command}"\ncontinues = false\n'
    )

    experiment, _ = asyncio.run(
        prepare_experiment(
            read_config(tmp_path / ".labnotes.toml"),
            "exp",
            Path("alt/experiment.toml"),
            None,
        )
    )

    assert experiment.command == command
