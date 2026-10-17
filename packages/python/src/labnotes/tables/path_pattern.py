import re

TOKEN = re.compile(r"\{([^}]*)\}|\*\*|\*|\?|[^{*?]+")


def path_pattern(template: str) -> re.Pattern[str]:
    parts = []
    for match in TOKEN.finditer(template):
        token = match.group(0)
        if match.group(1) is not None:
            parts.append(f"(?P<{match.group(1)}>[^/]+)")
        elif token == "**":
            parts.append(".*")
        elif token == "*":
            parts.append("[^/]*")
        elif token == "?":
            parts.append("[^/]")
        else:
            parts.append(re.escape(token))
    if template.endswith("/"):
        parts.append(".+")
    return re.compile("".join(parts))
