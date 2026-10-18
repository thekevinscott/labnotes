from pathlib import Path

from labnotes.runner.run_folder import run_folder


def test_fills_the_runs_path() -> None:
    assert run_folder(Path("/p"), "data/{experiment}/{run}", "exp", "r1") == Path(
        "/p/data/exp/r1"
    )
