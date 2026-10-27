import asyncio
import shutil
import subprocess
import time
from pathlib import Path

CGROUP_ROOT = Path("/sys/fs/cgroup")
PROC_ROOT = Path("/proc")
LABEL = "labnotes.run"


def _docker(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["docker", *args], capture_output=True, text=True, timeout=3, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def _cgroup_path(pid: int) -> Path | None:
    try:
        lines = (PROC_ROOT / str(pid) / "cgroup").read_text().splitlines()
    except OSError:
        return None
    for line in lines:
        if line.startswith("0::"):
            return CGROUP_ROOT / line[3:].lstrip("/")
    return None


def _usage(path: Path) -> int:
    current = int((path / "memory.current").read_text())
    try:
        stats = (path / "memory.stat").read_text().splitlines()
    except OSError:
        return current  # Include cache rather than lose the whole container sample.
    for line in stats:
        name, _, value = line.partition(" ")
        if name == "inactive_file":
            try:
                return max(0, current - int(value))
            except ValueError:
                return current
    return current


class ContainerMemory:
    """Track this run's Docker cgroups without starting a CLI process per sample."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.cgroups: dict[str, Path] = {}
        self.events: asyncio.subprocess.Process | None = None
        self.watcher: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if shutil.which("docker") is None:
            return
        since = str(int(time.time()) - 1)
        ids = await asyncio.to_thread(
            _docker,
            "ps",
            "--quiet",
            "--no-trunc",
            "--filter",
            f"label={LABEL}={self.run_id}",
        )
        if ids is None:
            return  # An unreachable daemon leaves process-tree sampling unchanged.
        for container_id in ids.splitlines():
            await self._add(container_id)
        try:
            self.events = await asyncio.create_subprocess_exec(
                "docker",
                "events",
                "--since",
                since,
                "--filter",
                "type=container",
                "--filter",
                f"label={LABEL}={self.run_id}",
                "--format",
                "{{.Actor.ID}} {{.Action}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError:
            return
        self.watcher = asyncio.create_task(self._watch())

    async def _add(self, container_id: str) -> None:
        raw_pid = await asyncio.to_thread(
            _docker, "inspect", "--format", "{{.State.Pid}}", container_id
        )
        if raw_pid is None:
            return
        try:
            pid = int(raw_pid.strip())
        except ValueError:
            return
        if pid > 0 and (path := _cgroup_path(pid)) is not None:
            self.cgroups[container_id] = path

    async def _watch(self) -> None:
        assert self.events is not None and self.events.stdout is not None
        while line := await self.events.stdout.readline():
            container_id, _, action = line.decode().strip().partition(" ")
            if action == "start":
                await self._add(container_id)
            elif action in {"die", "destroy", "stop"}:
                self.cgroups.pop(container_id, None)

    def usage(self) -> int:
        total = 0
        for path in self.cgroups.values():
            try:
                total += _usage(path)
            except (OSError, ValueError):
                pass  # A stopped container can remove its cgroup between samples.
        return total

    async def close(self) -> None:
        if self.watcher is not None:
            self.watcher.cancel()
            await asyncio.gather(self.watcher, return_exceptions=True)
        if self.events is not None:
            if self.events.returncode is None:
                self.events.terminate()
            try:
                await asyncio.wait_for(self.events.wait(), timeout=1)
            except TimeoutError:
                self.events.kill()
                await self.events.wait()
