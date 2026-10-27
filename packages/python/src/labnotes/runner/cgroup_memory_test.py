from pathlib import Path

from labnotes.runner.cgroup_memory import cgroup_memory


def test_counts_usage_without_inactive_file_cache(tmp_path: Path) -> None:
    (tmp_path / "memory.current").write_text("150\n")
    (tmp_path / "memory.stat").write_text("anon 90\ninactive_file 40\n")
    assert cgroup_memory(tmp_path) == 110


def test_clamps_cache_subtraction_at_zero(tmp_path: Path) -> None:
    (tmp_path / "memory.current").write_text("20\n")
    (tmp_path / "memory.stat").write_text("inactive_file 40\n")
    assert cgroup_memory(tmp_path) == 0


def test_counts_current_usage_when_cache_stats_are_unavailable(tmp_path: Path) -> None:
    (tmp_path / "memory.current").write_text("150\n")
    assert cgroup_memory(tmp_path) == 150


def test_counts_current_usage_when_cache_stats_are_invalid(tmp_path: Path) -> None:
    (tmp_path / "memory.current").write_text("150\n")
    (tmp_path / "memory.stat").write_text("inactive_file invalid\n")
    assert cgroup_memory(tmp_path) == 150


def test_counts_current_usage_without_inactive_file_stat(tmp_path: Path) -> None:
    (tmp_path / "memory.current").write_text("150\n")
    (tmp_path / "memory.stat").write_text("anon 90\n")
    assert cgroup_memory(tmp_path) == 150
