from pathlib import Path


def cgroup_memory(path: Path) -> int:
    current = int((path / "memory.current").read_text())
    try:
        stats = (path / "memory.stat").read_text().splitlines()
    except OSError:
        return current
    for line in stats:
        name, _, value = line.partition(" ")
        if name == "inactive_file":
            try:
                return max(0, current - int(value))
            except ValueError:
                return current
    return current
