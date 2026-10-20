import re
from pathlib import Path, PurePosixPath

DEFAULT_PATHS = {
    "experiments": "{experiment}",
    "files": "{experiment}/files/",
    "runs": "{experiment}/runs/{run}",
}
PLACEHOLDERS = {
    "experiments": {"experiment"},
    "files": {"experiment"},
    "runs": {"experiment", "run"},
}
# Keys other readers own, so the path check lets them through.
OTHER_KEYS = {"experiments": {"mode"}}
PLACEHOLDER = re.compile(r"\{([^}]*)\}")


def read_path(config: Path, table: str, section: object) -> str:
    if not isinstance(section, dict):
        raise ValueError(f"{config}: {table} must be a table, like [{table}]")
    unknown = sorted(section.keys() - {"path", *OTHER_KEYS.get(table, ())})
    if unknown:
        raise ValueError(f"{config}: unknown keys in [{table}]: {', '.join(unknown)}")
    template = section.get("path", DEFAULT_PATHS[table])
    if not isinstance(template, str):
        raise ValueError(f"{config}: [{table}] path must be a string")
    if PurePosixPath(template).is_absolute() or template.startswith("~"):
        raise ValueError(
            f"{config}: [{table}] path must be relative to the config's folder"
        )
    required = PLACEHOLDERS[table]
    if set(PLACEHOLDER.findall(template)) != required:
        expected = " and ".join(f"{{{name}}}" for name in sorted(required))
        raise ValueError(f"{config}: [{table}] path must use exactly {expected}")
    return template
