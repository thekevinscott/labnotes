import os
import shlex

from curtaincall import Terminal
from pathlib import Path


def test_uvx_run_rejects_an_escaping_runs_path_before_writing(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "alpha").mkdir(parents=True)
    (root / ".labnotes.toml").write_text(
        '[runs]\npath = "../escaped-{experiment}/{run}"\n'
    )
    (root / "alpha/experiment.toml").write_text(
        'command = "python3 -c pass"\ncontinues = false\n'
    )

    command = shlex.join(
        [
            "uvx",
            "labnotes",
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "alpha",
            "run",
        ]
    )
    term = Terminal(command, rows=30, cols=160, env={**os.environ, **uvx})
    term.start()
    try:
        assert term.wait(timeout=30) != 0
        assert "[runs] path must be relative" in term._get_screen_text()
        assert not (tmp_path / "escaped-alpha").exists()
    finally:
        term.kill()
