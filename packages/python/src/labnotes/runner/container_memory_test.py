import asyncio
from pathlib import Path
from unittest import mock

from labnotes.runner.container_memory import ContainerMemory


def test_absent_docker_keeps_container_memory_at_zero() -> None:
    async def check() -> None:
        with (
            mock.patch(
                "labnotes.runner.container_memory.shutil.which", return_value=None
            ),
            mock.patch("labnotes.runner.container_memory.docker_output") as docker,
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
            mock.patch(
                "labnotes.runner.container_memory.shutil.which",
                return_value="/usr/bin/docker",
            ),
            mock.patch(
                "labnotes.runner.container_memory.docker_output", return_value=None
            ),
            mock.patch(
                "labnotes.runner.container_memory.asyncio.create_subprocess_exec"
            ) as events,
        ):
            containers = ContainerMemory("run-a")
            await containers.start()
            assert containers.usage() == 0
            await containers.close()
        events.assert_not_called()

    asyncio.run(check())


def test_event_stream_failure_keeps_sampling_available() -> None:
    async def check() -> None:
        with (
            mock.patch(
                "labnotes.runner.container_memory.shutil.which",
                return_value="/usr/bin/docker",
            ),
            mock.patch("labnotes.runner.container_memory.docker_output", return_value=""),
            mock.patch(
                "labnotes.runner.container_memory.asyncio.create_subprocess_exec",
                side_effect=OSError("daemon unavailable"),
            ),
        ):
            containers = ContainerMemory("run-a")
            await containers.start()
            assert containers.usage() == 0
            await containers.close()

    asyncio.run(check())


def test_ignores_containers_without_a_readable_host_cgroup() -> None:
    async def check() -> None:
        containers = ContainerMemory("run-a")
        with (
            mock.patch(
                "labnotes.runner.container_memory.docker_output",
                side_effect=[None, "invalid", "0", "42"],
            ),
            mock.patch(
                "labnotes.runner.container_memory.container_cgroup",
                return_value=None,
            ),
        ):
            for _ in range(4):
                await containers._add("container-1")
        assert containers.cgroups == {}

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
            mock.patch(
                "labnotes.runner.container_memory.shutil.which",
                return_value="/usr/bin/docker",
            ),
            mock.patch(
                "labnotes.runner.container_memory.docker_output", side_effect=docker
            ),
            mock.patch(
                "labnotes.runner.container_memory.container_cgroup",
                return_value=tmp_path,
            ),
            mock.patch(
                "labnotes.runner.container_memory.asyncio.create_subprocess_exec",
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
            mock.patch(
                "labnotes.runner.container_memory.shutil.which",
                return_value="/usr/bin/docker",
            ),
            mock.patch(
                "labnotes.runner.container_memory.docker_output", side_effect=docker
            ) as commands,
            mock.patch(
                "labnotes.runner.container_memory.container_cgroup",
                return_value=tmp_path,
            ),
            mock.patch(
                "labnotes.runner.container_memory.asyncio.create_subprocess_exec",
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
            assert commands.call_count == 2
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


def test_kills_event_stream_if_termination_times_out() -> None:
    async def check() -> None:
        containers = ContainerMemory("run-a")
        process = mock.Mock(returncode=None)
        process.wait = mock.AsyncMock(side_effect=[TimeoutError, 0])
        containers.events = process
        await containers.close()
        process.terminate.assert_called_once()
        process.kill.assert_called_once()

    asyncio.run(check())


def test_ignores_other_events_and_stream_end() -> None:
    async def check() -> None:
        reader = asyncio.StreamReader()
        reader.feed_data(b"container-1 pause\n")
        reader.feed_eof()
        containers = ContainerMemory("run-a")
        containers.events = mock.Mock(stdout=reader)
        await containers._watch()
        assert containers.cgroups == {}

    asyncio.run(check())


def test_close_does_not_terminate_an_exited_event_stream() -> None:
    async def check() -> None:
        containers = ContainerMemory("run-a")
        process = mock.Mock(returncode=0)
        process.wait = mock.AsyncMock(return_value=0)
        containers.events = process
        await containers.close()
        process.terminate.assert_not_called()

    asyncio.run(check())
