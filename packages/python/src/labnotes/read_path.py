import re
from pathlib import Path, PurePosixPath

DEFAULT_PATHS = {
    "experiments": "{experiment}",
    "files": "{experiment}/files/",
    "runs": "{experiment}/runs/{run}",
}
# One experiment at the config's folder, so no {experiment} to fill.
SINGLE_PATHS = {"experiments": "", "files": "files/", "runs": "runs/{run}"}
PLACEHOLDERS = {
    "experiments": {"experiment"},
    "files": {"experiment"},
    "runs": {"experiment", "run"},
}
# Keys other readers own, so the path check lets them through.
OTHER_KEYS = {"experiments": {"mode", "concurrency"}}
PLACEHOLDER = re.compile(r"\{([^}]*)\}")
SINGLE = "experiment.toml sits next to .labnotes.toml, so this folder is the experiment"


def read_path(
    config: Path, table: str, section: object, *, single: bool = False
) -> str:
    if not isinstance(section, dict):
        raise ValueError(f"{config}: {table} must be a table, like [{table}]")
    unknown = sorted(section.keys() - {"path", *OTHER_KEYS.get(table, ())})
    if unknown:
        raise ValueError(f"{config}: unknown keys in [{table}]: {', '.join(unknown)}")
    defaults = SINGLE_PATHS if single else DEFAULT_PATHS
    if single and table == "experiments" and "path" in section:
        raise ValueError(f"{config}: [experiments] path doesn't apply; {SINGLE}")
    template = section.get("path", defaults[table])
    if not isinstance(template, str):
        raise ValueError(f"{config}: [{table}] path must be a string")
    if PurePosixPath(template).is_absolute() or template.startswith("~"):
        raise ValueError(
            f"{config}: [{table}] path must be relative to the config's folder"
        )
    used = set(PLACEHOLDER.findall(template))
    if single and "experiment" in used:
        raise ValueError(f"{config}: [{table}] path can't use {{experiment}}; {SINGLE}")
    required = PLACEHOLDERS[table] - ({"experiment"} if single else set())
    if used != required:
        expected = " and ".join(f"{{{name}}}" for name in sorted(required))
        if not expected:
            raise ValueError(f"{config}: [{table}] path can't use placeholders")
        raise ValueError(f"{config}: [{table}] path must use exactly {expected}")
    return template
