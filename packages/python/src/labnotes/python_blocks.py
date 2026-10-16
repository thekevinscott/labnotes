from markdown_it import MarkdownIt
from markdown_it.token import Token

_parser = MarkdownIt("commonmark")


def is_python(token: Token) -> bool:
    return token.type == "fence" and token.info.split()[:1] == ["python"]


def python_blocks(text: str) -> list[str]:
    return [token.content for token in _parser.parse(text) if is_python(token)]
