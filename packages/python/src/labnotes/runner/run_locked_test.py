import fcntl
from pathlib import Path

from labnotes.runner.run_locked import run_locked


def test_is_locked_while_someone_holds_the_lock(tmp_path: Path) -> None:
    with (tmp_path / "run.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)

        assert run_locked(tmp_path)


def test_is_free_once_the_holder_lets_go(tmp_path: Path) -> None:
    with (tmp_path / "run.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)

    assert not run_locked(tmp_path)
    assert not run_locked(tmp_path)
