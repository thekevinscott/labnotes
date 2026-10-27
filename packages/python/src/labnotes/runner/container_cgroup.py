from pathlib import Path

CGROUP_ROOT = Path("/sys/fs/cgroup")
PROC_ROOT = Path("/proc")


def container_cgroup(pid: int) -> Path | None:
    try:
        lines = (PROC_ROOT / str(pid) / "cgroup").read_text().splitlines()
    except OSError:
        return None
    for line in lines:
        if line.startswith("0::"):
            return CGROUP_ROOT / line.removeprefix("0::").lstrip("/")
    return None
