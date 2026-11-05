import sys
from collections.abc import Iterator
from pathlib import Path

from curtaincall import expect
import psutil
import pytest


@pytest.fixture(autouse=True)
def cleanup_daemons(tmp_path: Path) -> Iterator[None]:
    yield
    config = str(tmp_path / ".labnotes.toml")
    owners = [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (process.info["cmdline"] or [])
        and "daemon" in (process.info["cmdline"] or [])
    ]
    for process in owners:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(owners, timeout=15)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass


def test_run_rejects_an_env_key_that_is_not_a_shell_identifier(
    terminal, tmp_path: Path
) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp" / "experiment.toml").write_text(
        'command = "true"\ncontinues = false\n[env]\n"with-dash" = "x"\n'
    )
    labnotes = Path(sys.executable).parent / "labnotes"

    term = terminal(
        f"{labnotes} -c {tmp_path / '.labnotes.toml'} experiments exp run",
        rows=30,
        cols=120,
    )

    expect(term.get_by_text("env.with-dash must be a shell identifier")).to_be_visible()
    term.wait()
    assert term.exit_code == 1
    assert not list(tmp_path.glob("exp/runs/*/run.json"))
