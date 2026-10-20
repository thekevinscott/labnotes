import re

TOKEN = re.compile(r"\{([^}]*)\}|\*\*|\*|\?|[^{*?]+")


def path_pattern(template: str) -> re.Pattern[str]:
    parts = []
    for found in TOKEN.finditer(template):
        if found.group(1) == "run":
            parts.append("(?P<run>[^/]+(?:/[^/]+)?)")
            continue
        if found.group(1) is not None:
            parts.append(f"(?P<{found.group(1)}>[^/]+)")
            continue
        match found.group(0):
            case "**":
                parts.append(".*")
            case "*":
                parts.append("[^/]*")
            case "?":
                parts.append("[^/]")
            case token:
                parts.append(re.escape(token))
    if template.endswith("/"):
        parts.append(".+")
    return re.compile("".join(parts))
