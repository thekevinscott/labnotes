import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from curtaincall import Terminal, expect

PACKAGE = Path(__file__).parents[2]
MOD = PACKAGE.parents[1] / "skills" / "labnotes"
PROMPT = re.compile(r"shift\+tab to cycle|\? for shortcuts")
RUN_A = re.compile(r"a-[0-9a-f]{4} +--m a")
RUN_B = re.compile(r"b-[0-9a-f]{4} +--m b")


@pytest.fixture
def uvx(tmp_path: Path) -> dict[str, str]:
    # The mod runs `uvx labnotes`. With this checkout installed as the uv tool,
    # uvx runs it, offline, rather than a published release.
    env = {"UV_NO_CONFIG": "1", "UV_TOOL_DIR": str(tmp_path / "tools")}
    constraints = tmp_path / "constraints.txt"
    uv = ["uv", "--directory", str(PACKAGE)]
    subprocess.run(
        [*uv, "export", "-q", "--frozen", "--no-dev", "--no-emit-project"]
        + ["-o", str(constraints)],
        check=True,
    )
    subprocess.run(
        [*uv, "tool", "install", "-q", "-c", str(constraints), "."],
        check=True,
        env={**os.environ, **env, "UV_TOOL_BIN_DIR": str(tmp_path / "bin")},
    )
    return {**env, "UV_OFFLINE": "1"}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "exp").mkdir(parents=True)
    (project / ".labnotes.toml").write_text("")
    command = f"{shlex.quote(sys.executable)} -c 'import time; time.sleep(120)'"
    (project / "exp" / "experiment.toml").write_text(
        f'command = """{command}"""\n[params]\nm = ["a", "b"]\n'
    )
    return project


@pytest.fixture
def home(tmp_path: Path, project: Path) -> Path:
    # Enough for claude to reach its prompt with no account and no model turn.
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"apiKeyHelper": "echo sk-ant-e2e-dummy"})
    )
    (home / ".claude.json").write_text(
        json.dumps(
            {
                "hasCompletedOnboarding": True,
                "projects": {str(project): {"hasTrustDialogAccepted": True}},
            }
        )
    )
    return home


@pytest.fixture
def runs(project: Path) -> Iterator[None]:
    labnotes = [
        Path(sys.executable).parent / "labnotes",
        "-c",
        project / ".labnotes.toml",
    ]
    process = subprocess.Popen(
        [*labnotes, "experiments", "exp", "run"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        yield
    finally:
        subprocess.run([*labnotes, "run", "stop"], capture_output=True)
        process.terminate()
        process.wait()


@pytest.fixture
def claude(terminal, project: Path, home: Path, uvx: dict[str, str]) -> Terminal:
    claude = shutil.which("claude")
    assert claude is not None, "claude is not installed"
    return terminal(
        f"env -C {shlex.quote(str(project))} {shlex.quote(claude)}"
        f" --plugin-dir {shlex.quote(str(MOD))}",
        rows=40,
        cols=160,
        env={
            **uvx,
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_AUTOUPDATER": "1",
        },
    )


def click(term: Terminal, text: re.Pattern[str]) -> None:
    # curtaincall has no mouse helper: an SGR mouse press and release.
    cell = term.get_by_text(text).cells[0]
    at = f"{cell.col + 1};{cell.row + 1}"
    term.write(f"\x1b[<0;{at}M\x1b[<0;{at}m")


def test_the_pane_shows_runs_and_stops_one(claude: Terminal, runs: None) -> None:
    expect(claude.get_by_text(PROMPT)).to_be_visible(timeout=60)
    claude.write("/labnotes-runs")
    expect(claude.get_by_text("live table of this project's runs")).to_be_visible()
    claude.key_enter()
    expect(claude.get_by_text("labnotes pane opened")).to_be_visible()
    expect(claude.get_by_text(RUN_A)).to_be_visible(timeout=30)
    expect(claude.get_by_text(RUN_B)).to_be_visible()

    click(claude, RUN_A)
    claude.write("x")
    expect(
        claude.get_by_text(re.compile(r"Stopping \S+/a-[0-9a-f]{4}\."))
    ).to_be_visible()
    expect(
        claude.get_by_text(re.compile(RUN_A.pattern + " +✗ exited -15"))
    ).to_be_visible()
    expect(
        claude.get_by_text(re.compile(RUN_B.pattern + r" +\S +\d+s"))
    ).to_be_visible()
