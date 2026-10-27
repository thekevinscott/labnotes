from pathlib import Path
from unittest import mock

from labnotes.runner.container_cgroup import container_cgroup


def test_reads_the_host_cgroup_of_a_container_pid(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    (proc / "42").mkdir(parents=True)
    (proc / "42" / "cgroup").write_text("0::/system.slice/docker-example.scope\n")
    with (
        mock.patch("labnotes.runner.container_cgroup.PROC_ROOT", proc),
        mock.patch("labnotes.runner.container_cgroup.CGROUP_ROOT", tmp_path / "cgroup"),
    ):
        path = container_cgroup(42)
    assert path == tmp_path / "cgroup/system.slice/docker-example.scope"


def test_missing_process_has_no_cgroup(tmp_path: Path) -> None:
    with mock.patch("labnotes.runner.container_cgroup.PROC_ROOT", tmp_path):
        assert container_cgroup(42) is None
