import asyncio
from pathlib import Path
from unittest import mock

from labnotes.runner import container_memory
from labnotes.runner.container_memory import ContainerMemory


def test_reads_the_host_cgroup_of_a_container_pid(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    (proc / "42").mkdir(parents=True)
    (proc / "42" / "cgroup").write_text("0::/system.slice/docker-example.scope\n")
    with (
        mock.patch.object(container_memory, "PROC_ROOT", proc),
        mock.patch.object(container_memory, "CGROUP_ROOT", tmp_path / "cgroup"),
    ):
        path = container_memory._cgroup_path(42)
    assert path == tmp_path / "cgroup/system.slice/docker-example.scope"


def test_counts_usage_without_inactive_file_cache(tmp_path: Path) -> None:
    (tmp_path / "memory.current").write_text("150\n")
    (tmp_path / "memory.stat").write_text("anon 90\ninactive_file 40\n")
    assert container_memory._usage(tmp_path) == 110


def test_clamps_cache_subtraction_at_zero(tmp_path: Path) -> None:
    (tmp_path / "memory.current").write_text("20\n")
    (tmp_path / "memory.stat").write_text("inactive_file 40\n")
    assert container_memory._usage(tmp_path) == 0


def test_counts_current_usage_when_cache_stats_are_unavailable(tmp_path: Path) -> None:
    (tmp_path / "memory.current").write_text("150\n")
    assert container_memory._usage(tmp_path) == 150


def test_absent_docker_keeps_container_memory_at_zero() -> None:
    async def check() -> None:
        with (
            mock.patch.object(container_memory.shutil, "which", return_value=None),
            mock.patch.object(container_memory, "_docker") as docker,
        ):
            containers = ContainerMemory("run-a")
            await containers.start()
            assert containers.usage() == 0
            await containers.close()
        docker.assert_not_called()

    asyncio.run(check())


def test_unreachable_docker_does_not_start_an_event_stream() -> None:
    async def check() -> None:
        with (
            mock.patch.object(
                container_memory.shutil, "which", return_value="/usr/bin/docker"
            ),
            mock.patch.object(container_memory, "_docker", return_value=None),
            mock.patch.object(
                container_memory.asyncio, "create_subprocess_exec"
            ) as events,
        ):
            containers = ContainerMemory("run-a")
            await containers.start()
            assert containers.usage() == 0
            await containers.close()
        events.assert_not_called()

    asyncio.run(check())


def test_finds_containers_already_running_when_sampling_starts(tmp_path: Path) -> None:
    async def check() -> None:
        (tmp_path / "memory.current").write_text("150\n")
        (tmp_path / "memory.stat").write_text("inactive_file 40\n")
        process = mock.Mock(stdout=asyncio.StreamReader(), returncode=None)
        process.wait = mock.AsyncMock(return_value=0)

        def docker(*args: str) -> str:
            return "container-1\n" if args[0] == "ps" else "42\n"

        with (
            mock.patch.object(
                container_memory.shutil, "which", return_value="/usr/bin/docker"
            ),
            mock.patch.object(container_memory, "_docker", side_effect=docker),
            mock.patch.object(container_memory, "_cgroup_path", return_value=tmp_path),
            mock.patch.object(
                container_memory.asyncio,
                "create_subprocess_exec",
                new=mock.AsyncMock(return_value=process),
            ),
        ):
            containers = ContainerMemory("run-a")
            await containers.start()
            assert containers.usage() == 110
            await containers.close()

    asyncio.run(check())


def test_tracks_labeled_container_starts_and_stops_without_polling(
    tmp_path: Path,
) -> None:
    async def check() -> None:
        (tmp_path / "memory.current").write_text("150\n")
        (tmp_path / "memory.stat").write_text("inactive_file 40\n")
        reader = asyncio.StreamReader()
        process = mock.Mock(stdout=reader, returncode=None)
        process.wait = mock.AsyncMock(return_value=0)

        def docker(*args: str) -> str:
            return "" if args[0] == "ps" else "42\n"

        with (
            mock.patch.object(
                container_memory.shutil, "which", return_value="/usr/bin/docker"
            ),
            mock.patch.object(
                container_memory, "_docker", side_effect=docker
            ) as commands,
            mock.patch.object(container_memory, "_cgroup_path", return_value=tmp_path),
            mock.patch.object(
                container_memory.asyncio,
                "create_subprocess_exec",
                new=mock.AsyncMock(return_value=process),
            ) as events,
        ):
            containers = ContainerMemory("run-a")
            await containers.start()
            reader.feed_data(b"container-1 start\n")
            for _ in range(100):
                if containers.usage() == 110:
                    break
                await asyncio.sleep(0.01)
            assert containers.usage() == 110
            assert (
                commands.call_count == 2
            )  # docker ps once, inspect once; samples read files only.
            assert events.await_args is not None
            assert "label=labnotes.run=run-a" in events.await_args.args
            reader.feed_data(b"container-1 die\n")
            for _ in range(100):
                if containers.usage() == 0:
                    break
                await asyncio.sleep(0.01)
            assert containers.usage() == 0
            await containers.close()
        process.terminate.assert_called_once()

    asyncio.run(check())


def test_disappeared_cgroup_does_not_break_a_sample(tmp_path: Path) -> None:
    containers = ContainerMemory("run-a")
    containers.cgroups["gone"] = tmp_path / "missing"
    assert containers.usage() == 0
