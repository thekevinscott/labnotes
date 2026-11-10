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
    expected_error: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run an installed CLI command in its real TUI PTY and collect its outcome."""
    import re
    import shlex
    from curtaincall import Terminal, expect

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
    try:
        if expected_error is not None:
            expect(term.get_by_text(expected_error)).to_be_visible(timeout=timeout)
            code = term.wait(timeout=10)
            assert code != 0, term.to_snapshot()
            screen = "\n".join(
                "".join(row).rstrip() for row in term.get_viewable_buffer()
            )
            return subprocess.CompletedProcess(args, code, screen, screen)
        expect(term.get_by_text(summary)).to_be_visible(timeout=timeout)
        expect(term.get_by_text("Ctrl-C to quit.")).to_be_visible()
        screen = "\n".join("".join(row).rstrip() for row in term.get_viewable_buffer())
        found = summary.search(screen)
        assert found is not None, term.to_snapshot()
        term.key_ctrl_c()
        code = term.wait(timeout=10)
        assert code == 0, term.to_snapshot()
        return subprocess.CompletedProcess(
            args, code, screen + "\n" + found.group() + "\n", ""
        )
    finally:
        term.kill()
