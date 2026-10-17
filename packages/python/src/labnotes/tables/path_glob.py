import re

PLACEHOLDER = re.compile(r"\{[^}]*\}")


def path_glob(template: str) -> str:
    glob = PLACEHOLDER.sub("*", template)
    return f"{glob}**" if glob.endswith("/") else glob
