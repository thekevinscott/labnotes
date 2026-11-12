import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from curtaincall import expect

from conftest import Tui


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        yield Path(folder)


def test_installed_daemon_reuses_socket_and_stop_cli(
    tmp_path: Path, uvx: dict[str, str], tui: Tui, runtime: Path
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "exp/experiment.toml").write_text(
        "continues = false\n"
        f'command = "{sys.executable} -c \'print(\\"sleeping\\", flush=True); '
        "import time; time.sleep(600)'\"\n"
    )
    env = {**os.environ, **uvx, "XDG_RUNTIME_DIR": str(runtime)}
    base = ["uvx", "labnotes", "-c", str(root / ".labnotes.toml")]

    term = tui(root, "experiments", "exp", "run", env={"XDG_RUNTIME_DIR": str(runtime)})
    expect(term.get_by_text("sleeping")).to_be_visible(timeout=120)
    term.key_ctrl_c()
    expect(term.get_by_text("leave running (enter or l)")).to_be_visible()
    term.write("l")
    assert tui.exited(term) == 0, term.to_snapshot()
    expect(
        term.get_by_text("Stop it with: labnotes experiments exp stop")
    ).to_be_visible()
    [path] = runtime.glob("labnotes/*.sock")

    second = subprocess.run(
        [*base, "daemon", "exp"], cwd=root, env=env, stdout=subprocess.DEVNULL
    )
    assert second.returncode == 0
    assert list(runtime.glob("labnotes/*.sock")) == [path]
    stopped = subprocess.run(
        [*base, "experiments", "exp", "stop"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert stopped.returncode == 0, stopped.stderr
    [record_path] = root.glob("exp/runs/*/run.json")
    for _ in range(100):
        record = json.loads(record_path.read_text())
        if record.get("ended") is not None:
            break
        time.sleep(0.05)
    assert record["ended_by"] == "stop"
