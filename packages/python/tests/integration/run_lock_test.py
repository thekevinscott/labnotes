import fcntl
import os
from pathlib import Path

from labnotes.runner.claim_run import claim_run
from labnotes.runner.run_locked import run_locked


def test_a_claimed_run_is_locked_until_let_go(tmp_path: Path) -> None:
    (tmp_path / "run.lock").write_text("left behind")

    lock = claim_run(tmp_path)

    assert lock is not None
    assert (tmp_path / "run.lock").read_text() == "left behind"
    assert claim_run(tmp_path) is None
    assert run_locked(tmp_path)
    os.close(lock)
    assert not run_locked(tmp_path)


def test_a_lock_held_by_another_process_blocks_the_claim(tmp_path: Path) -> None:
    with (tmp_path / "run.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)

        assert claim_run(tmp_path) is None
        assert run_locked(tmp_path)

    lock = claim_run(tmp_path)
    assert lock is not None
    assert not os.get_inheritable(lock)
    os.close(lock)
