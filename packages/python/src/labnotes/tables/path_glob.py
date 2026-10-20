import re

PLACEHOLDER = re.compile(r"\{[^}]*\}")


def path_glob(template: str) -> str:
    glob = PLACEHOLDER.sub("*", template.replace("{run}", "**"))
    return f"{glob}**" if glob.endswith("/") else glob
