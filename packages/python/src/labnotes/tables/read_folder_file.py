from pathlib import Path


def read_folder_file(folder: Path, path: str) -> list[dict[str, object]]:
    try:
        size = Path(path).stat().st_size
    except FileNotFoundError:
        return []
    return [{"path": Path(path).relative_to(folder).as_posix(), "size": size}]
