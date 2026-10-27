import asyncio
import shutil
import time
from pathlib import Path

from labnotes.runner.cgroup_memory import cgroup_memory
from labnotes.runner.container_cgroup import container_cgroup
from labnotes.runner.docker_output import docker_output

LABEL = "labnotes.run"


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
        since = str(int(time.time()))
        ids = await asyncio.to_thread(
            docker_output,
            "ps",
            "--quiet",
            "--no-trunc",
            "--filter",
            f"label={LABEL}={self.run_id}",
        )
        if ids is None:
            return
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
            docker_output, "inspect", "--format", "{{.State.Pid}}", container_id
        )
        if raw_pid is None:
            return
        try:
            pid = int(raw_pid.strip())
        except ValueError:
            return
        if pid > 0 and (path := container_cgroup(pid)) is not None:
            self.cgroups[container_id] = path

    async def _watch(self) -> None:
        assert self.events is not None
        assert self.events.stdout is not None
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
                total += cgroup_memory(path)
            except (OSError, ValueError):
                pass
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
