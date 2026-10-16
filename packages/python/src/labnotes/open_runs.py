from pathlib import Path

from dirsql import DirSQL


def open_runs(folder: Path) -> DirSQL:
    config = folder / ".dirsql.toml"
    if not config.is_file():
        raise FileNotFoundError(
            f"{config} not found; the data folder needs a dirsql config"
        )
    # Run data is usually gitignored (DVC, large outputs), so scan it anyway.
    return DirSQL(str(folder), config=[str(config)], no_ignore=True)
