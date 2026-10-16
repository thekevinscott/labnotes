from markdown_it import MarkdownIt

_markdown = MarkdownIt("commonmark", {"html": False, "typographer": True}).enable(
    ["table", "strikethrough", "replacements", "smartquotes"]
)


def render_markdown(text: str) -> str:
    return _markdown.render(text)
