import json
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from curtaincall import expect

from conftest import Tui


def wait_for(check, seconds: float = 30) -> None:
    deadline = time.monotonic() + seconds
    while not check() and time.monotonic() < deadline:
        time.sleep(0.05)


def restarts(root: Path) -> list[str]:
    return [
        path.parent.name
        for path in root.glob("exp/runs/*/run.json")
        if json.loads(path.read_text()).get("retry_of")
    ]


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        yield Path(folder)


def test_installed_tui_leaves_then_two_tuis_reattach(
    tmp_path: Path, tui: Tui, runtime: Path
) -> None:
    release = tmp_path / "release"
    (tmp_path / "exp").mkdir()
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "hold.py").write_text(
        "import time\nfrom pathlib import Path\n"
        f"while not Path({str(release)!r}).exists():\n    time.sleep(0.05)\n"
    )
    (tmp_path / "exp/experiment.toml").write_text(
        f'continues = false\nrepeats = 2\ncommand = "{sys.executable} hold.py"\n'
    )
    env = {"XDG_RUNTIME_DIR": str(runtime)}

    idle = tui(tmp_path, "experiments", "exp", "attach", env=env, cols=120)
    expect(idle.get_by_text("Nothing is running for exp.")).to_be_visible(timeout=60)
    assert tui.exited(idle) == 0
    assert not list(runtime.glob("labnotes/*.sock"))

    first = tui(tmp_path, "experiments", "exp", "run", env=env, cols=120)
    try:
        expect(first.get_by_text("1 at a time")).to_be_visible(timeout=60)
        first.key_ctrl_c()
        expect(first.get_by_text("leave running")).to_be_visible()
        first.write("l")
        expect(
            first.get_by_text("Reattach with: labnotes experiments exp attach")
        ).to_be_visible(timeout=10)
        assert tui.exited(first) == 0

        attached = [
            tui(tmp_path, "experiments", "exp", "attach", env=env, cols=120)
            for _ in range(2)
        ]
        for term in attached:
            expect(term.get_by_text("1 at a time")).to_be_visible(timeout=60)
        attached[0].write("+")
        for term in attached:
            expect(term.get_by_text("2 at a time")).to_be_visible(timeout=10)
        release.write_text("")
        for term in attached:
            expect(term.get_by_text("2 passed, 0 failed.")).to_be_visible(timeout=30)
            tui.quit(term)
    finally:
        release.write_text("")


def test_installed_tuis_attached_together_both_follow_a_restart(
    tmp_path: Path, tui: Tui, runtime: Path
) -> None:
    release = tmp_path / "release"
    (tmp_path / "exp").mkdir()
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "fail-once").write_text("")
    (tmp_path / "script.py").write_text(
        "import sys, time\nfrom pathlib import Path\n"
        "m = sys.argv[sys.argv.index('--m') + 1]\n"
        "if m == 'a' and Path('fail-once').exists():\n"
        "    Path('fail-once').unlink()\n    sys.exit(1)\n"
        f"while not Path({str(release)!r}).exists():\n    time.sleep(0.05)\n"
    )
    (tmp_path / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\n'
        'continues = false\nretries = 0\nconcurrency = 2\n[params]\nm = ["a", "b"]\n'
    )
    env = {"XDG_RUNTIME_DIR": str(runtime)}

    first = tui(tmp_path, "experiments", "exp", "run", env=env)
    try:
        expect(first.get_by_text("✗ exited 1")).to_be_visible(timeout=60)
        first.key_ctrl_c()
        expect(first.get_by_text("leave running")).to_be_visible()
        first.write("l")
        assert tui.exited(first) == 0

        attached = [
            tui(tmp_path, "experiments", "exp", "attach", env=env) for _ in range(2)
        ]
        for term in attached:
            expect(term.get_by_text("✗ exited 1")).to_be_visible(timeout=60)
        attached[0].write("r")
        wait_for(lambda: bool(restarts(tmp_path)))
        [restarted] = restarts(tmp_path)
        for term in attached:
            expect(term.get_by_text(restarted)).to_be_visible(timeout=30)
        release.write_text("")
        for term in attached:
            expect(term.get_by_text("2 passed, 0 failed. 1 retried.")).to_be_visible(
                timeout=60
            )
            tui.quit(term)
    finally:
        release.write_text("")
