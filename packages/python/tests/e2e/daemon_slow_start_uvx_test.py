import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import psutil
from curtaincall import Terminal, expect
from curtaincall.expect import LocatorAssertions


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
    _, alive = psutil.wait_procs(owners, timeout=15)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass


def wait_for(term: Terminal, text: str, timeout: float) -> None:
    assertions = expect(term.get_by_text(text))
    assert isinstance(assertions, LocatorAssertions)
    assertions.to_be_visible(timeout=timeout)


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True)


def test_uvx_tui_waits_for_slow_run_start(tmp_path: Path, uvx: dict[str, str]) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text("continues = false\ncommand = 'true'\n")
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "-c", "user.name=T", "-c", "user.email=t@e.x", "commit", "-qm", "init")

    real_git = shutil.which("git")
    assert real_git is not None
    wrappers = tmp_path / "bin-slow-git"
    wrappers.mkdir()
    marker = tmp_path / "clone-delayed"
    (wrappers / "git").write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = clone ]; then touch {shlex.quote(str(marker))}; sleep 11; fi\n'
        f'exec {shlex.quote(real_git)} "$@"\n'
    )
    (wrappers / "git").chmod(0o755)

    config = str(root / ".labnotes.toml")
    args = ["uvx", "labnotes", "-c", config, "experiments", "exp", "run"]
    line = f"cd {shlex.quote(str(root))} && exec {shlex.join(args)}"
    with TemporaryDirectory(prefix="ln-runtime-") as runtime:
        term = Terminal(
            "/bin/sh -c " + shlex.quote(line),
            rows=30,
            cols=200,
            env={
                **os.environ,
                **uvx,
                "PATH": f"{wrappers}:{os.environ['PATH']}",
                "XDG_RUNTIME_DIR": runtime,
            },
        )
        term.start()
        try:
            wait_for(term, "palette", timeout=5)
            wait_for(term, "1 passed, 0 failed.", timeout=45)
            assert marker.exists(), "run start was not slowed"
            assert not term.get_by_text("Start failed.").is_visible()
            assert not term.get_by_text("No daemon is running").is_visible()
            assert list(Path(runtime).glob("labnotes/*.sock")), "daemon socket gone"
            term.key_ctrl_c()
            assert term.wait(timeout=10) == 0, term.to_snapshot()
            [record] = [
                json.loads(path.read_text())
                for path in root.glob("exp/runs/*/run.json")
            ]
            assert record["exit_code"] == 0
        finally:
            term.kill()
            stop_daemons(config)
