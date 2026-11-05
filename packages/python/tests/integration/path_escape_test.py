from pathlib import Path

import pytest

from labnotes.read_config import read_config


@pytest.mark.parametrize(
    ("table", "template"),
    [
        ("experiments", "../outside/{experiment}"),
        ("files", "../outside/{experiment}/files"),
        ("runs", "../outside-{experiment}/{run}"),
    ],
)
def test_project_config_rejects_paths_outside_its_root(
    tmp_path: Path, table: str, template: str
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    config = root / ".labnotes.toml"
    config.write_text(f'[{table}]\npath = "{template}"\n')

    with pytest.raises(ValueError, match=f"\\[{table}\\] path must be relative"):
        read_config(config)
