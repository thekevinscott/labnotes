import re

GLOB = re.compile(r"[*?\[]")


def file_prefix(template: str) -> str:
    glob = GLOB.search(template)
    head = template[: glob.start()] if glob else template
    return head if head.endswith("/") else head[: head.rfind("/") + 1]
