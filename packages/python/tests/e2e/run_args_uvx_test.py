import os
import subprocess
import sys
from pathlib import Path


def test_uvx_args_override_a_flag_in_the_command(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text("import sys\nprint(*sys.argv[1:])\n")
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} script.py --memory 8g --output {{run_dir}}"\n'
    )

    result = subprocess.run(
        ["uvx", "labnotes", "-c", str(root / ".labnotes.toml")]
        + ["experiments", "exp", "run", "--", "--memory", "24g", "--auth", "api"],
        cwd=root,
        env={**os.environ, **uvx},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    [log] = root.glob("exp/runs/**/stdout.log")
    received = log.read_text().split()
    assert received[:2] == ["--memory", "24g"]
    assert received[2] == "--output"
    assert received[4:] == ["--auth", "api"]
