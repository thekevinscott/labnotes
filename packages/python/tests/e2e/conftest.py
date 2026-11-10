import os
import shlex
import signal
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import psutil
import pytest
from curtaincall import Terminal, expect

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


def crashed(term: Terminal) -> str | None:
    if term.get_by_text("Traceback").is_visible():
        return "printed a traceback"
    if not term.is_alive:
        return "exited before the test quit it"
    return None


class Tui:
    """Opens `uvx labnotes` in a real terminal and fails the test if it dies."""

    def __init__(self, terminal: Callable[..., Terminal], uvx: dict[str, str]):
        self.terminal = terminal
        self.uvx = uvx
        self.open: list[Terminal] = []
        self.launched: list[Terminal] = []
        self.configs: list[str] = []

    def __call__(
        self,
        root: Path,
        *argv: str,
        env: dict[str, str] | None = None,
        unset: tuple[str, ...] = (),
        rows: int = 30,
        cols: int = 200,
    ) -> Terminal:
        config = str(root / ".labnotes.toml")
        # curtaincall has no cwd option and can only add to the environment.
        args = ["env", *(f"--unset={name}" for name in unset)]
        args += ["uvx", "labnotes", "-c", config, *argv]
        line = f"cd {shlex.quote(str(root))} && exec {shlex.join(args)}"
        term = self.terminal(
            "/bin/sh -c " + shlex.quote(line),
            rows=rows,
            cols=cols,
            env={
                **(env or {}),
                **self.uvx,
                "LABNOTES_E2E_TUI": str(len(self.launched)),
            },
        )
        self.open.append(term)
        self.launched.append(term)
        self.configs.append(config)
        return term

    def signal(self, term: Terminal, number: int) -> None:
        """Crash or freeze a TUI on purpose; curtaincall has no signal API."""
        if number == signal.SIGKILL:
            self.open.remove(term)
        index = self.launched.index(term)
        marker, config = str(index), self.configs[index]
        for process in psutil.process_iter(["cmdline"]):
            cmdline = process.info["cmdline"] or []
            try:
                if config not in cmdline or "daemon" in cmdline:
                    continue
                if process.environ().get("LABNOTES_E2E_TUI") == marker:
                    process.send_signal(number)
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                pass

    def check(self, term: Terminal) -> None:
        if (problem := crashed(term)) is not None:
            pytest.fail(f"TUI {problem}:\n{term.to_snapshot()}", pytrace=False)

    def quit(self, term: Terminal) -> None:
        self.check(term)
        self.open.remove(term)
        term.key_ctrl_c()
        expect(term).to_have_exited()
        assert not term.get_by_text("Traceback").is_visible(), term.to_snapshot()
        assert term.exit_code == 0, term.to_snapshot()

    def stop(self, term: Terminal) -> None:
        self.check(term)
        term.key_ctrl_c()
        expect(term.get_by_text("Stop (s)")).to_be_visible()
        term.write("s")
        assert self.exited(term) == 0, term.to_snapshot()

    def exited(self, term: Terminal) -> int | None:
        self.open.remove(term)
        expect(term).to_have_exited(timeout=60)
        assert not term.get_by_text("Traceback").is_visible(), term.to_snapshot()
        return term.exit_code

    def stop_daemons(self) -> None:
        owners = [
            process
            for process in psutil.process_iter(["cmdline"])
            if "daemon" in (cmdline := process.info["cmdline"] or [])
            and any(config in cmdline for config in self.configs)
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


@pytest.fixture
def tui(terminal: Callable[..., Terminal], uvx: dict[str, str]) -> Iterator[Tui]:
    opened = Tui(terminal, uvx)
    yield opened
    try:
        for term in opened.open:
            opened.check(term)
    finally:
        opened.stop_daemons()
