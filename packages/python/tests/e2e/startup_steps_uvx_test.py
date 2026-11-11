import os
import re
import shlex
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import psutil
from curtaincall import Terminal, expect
from curtaincall.expect import LocatorAssertions

STEPS = ["Starting up", "Preparing experiment", "Preparing codebase", "Starting run"]
STEP_LINE = re.compile(r"^\s*[✓|/\\-] (\S.*?)\s*$")


def stop_daemons(config: str) -> None:
    owners = [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (cmdline := process.info["cmdline"] or []) and "daemon" in cmdline
    ]
    for process in owners:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(owners, timeout=15)


def wait_for(term: Terminal, text: str, timeout: float) -> None:
    assertions = expect(term.get_by_text(text))
    assert isinstance(assertions, LocatorAssertions)
    assertions.to_be_visible(timeout=timeout)


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True)


def shown_steps(term: Terminal, gate: Path) -> list[str]:
    # The meta command holds the start until the gate opens.
    wait_for(term, "Starting run", timeout=45)
    screen = term.screen_text()
    gate.touch()
    return [
        match.group(1)
        for line in screen.splitlines()
        if (match := STEP_LINE.match(line))
    ]


def test_uvx_startup_shows_each_merged_step_once(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    gate = tmp_path / "gate"
    hold = f"while [ ! -e {shlex.quote(str(gate))} ]; do sleep 0.1; done; echo '{{}}'"
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        f"continues = false\ncommand = 'true'\nmeta = '''{hold}'''\n"
    )
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "-c", "user.name=T", "-c", "user.email=t@e.x", "commit", "-qm", "init")

    config = str(root / ".labnotes.toml")
    args = ["uvx", "labnotes", "-c", config, "experiments", "exp", "run"]
    line = f"cd {shlex.quote(str(root))} && exec {shlex.join(args)}"
    with TemporaryDirectory(prefix="ln-runtime-") as runtime:
        env = {**os.environ, **uvx, "XDG_RUNTIME_DIR": runtime}
        try:
            for daemon_running in (False, True):
                sockets = list(Path(runtime).glob("labnotes/*.sock"))
                assert bool(sockets) == daemon_running
                gate.unlink(missing_ok=True)
                term = Terminal(
                    "/bin/sh -c " + shlex.quote(line), rows=30, cols=200, env=env
                )
                term.start()
                try:
                    steps = shown_steps(term, gate)
                    assert steps == STEPS, (daemon_running, term.to_snapshot())
                    wait_for(term, "1 passed, 0 failed.", timeout=30)
                    term.key_ctrl_c()
                    assert term.wait(timeout=10) == 0, term.to_snapshot()
                finally:
                    term.kill()
        finally:
            stop_daemons(config)
