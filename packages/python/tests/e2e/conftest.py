import os
import subprocess
from pathlib import Path

import pytest

PACKAGE = Path(__file__).parents[2]


@pytest.fixture
def uvx(tmp_path: Path) -> dict[str, str]:
    # Install this checkout as the uv tool so uvx runs it offline.
    env = {"UV_NO_CONFIG": "1", "UV_TOOL_DIR": str(tmp_path / "tools")}
    constraints = tmp_path / "constraints.txt"
    uv = ["uv", "--directory", str(PACKAGE)]
    subprocess.run(
        [*uv, "export", "-q", "--frozen", "--no-dev", "--no-emit-project"]
        + ["-o", str(constraints)],
        check=True,
    )
    # Rebuild labnotes so uncommitted source changes are tested, too.
    subprocess.run(
        [*uv, "tool", "install", "-q", "--refresh-package", "labnotes"]
        + ["-c", str(constraints), "."],
        check=True,
        env={**os.environ, **env, "UV_TOOL_BIN_DIR": str(tmp_path / "bin")},
    )
    return {**env, "UV_OFFLINE": "1"}


def run_uvx_tui(
    root: Path,
    uvx: dict[str, str],
    *argv: str,
    timeout: float = 120,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run an installed CLI command in its real TUI PTY and collect its outcome."""
    import re
    import shlex
    import time

    from curtaincall import Terminal

    args = ["uvx", "labnotes", "-c", str(root / ".labnotes.toml"), *argv]
    command = "/bin/sh -c " + shlex.quote(
        f"cd {shlex.quote(str(root))} && exec {shlex.join(args)}"
    )
    term = Terminal(
        command,
        rows=30,
        cols=300,
        env={**(env if env is not None else os.environ), **uvx},
    )
    term.start()
    summary = re.compile(r"\d+ passed, \d+ failed\.(?: \d+ retried\.)?")
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            screen = term._get_screen_text()
            found = summary.search(screen)
            if found:
                term.key_ctrl_c()
                code = term.wait(timeout=10)
                return subprocess.CompletedProcess(
                    args, code, screen + "\n" + found.group() + "\n", ""
                )
            if not term.is_alive:
                code = term.wait(timeout=2)
                return subprocess.CompletedProcess(args, code, screen, screen)
            time.sleep(0.05)
        raise TimeoutError(
            f"TUI did not finish within {timeout}s: {term.to_snapshot()}"
        )
    finally:
        term.kill()
