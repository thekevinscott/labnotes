from pathlib import Path, PurePosixPath

WILDCARDS = set("{*?[")


def runs_folder(root: Path, template: str, experiment: str) -> Path:
    filled = template.replace("{experiment}", experiment)
    parts = PurePosixPath(filled).parts
    literal = []
    for part in parts:
        if WILDCARDS & set(part):
            break
        literal.append(part)
    return root.joinpath(*literal)
