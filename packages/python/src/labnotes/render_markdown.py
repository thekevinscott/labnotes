from collections.abc import MutableMapping, Sequence
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token

from labnotes.python_blocks import is_python

_markdown = MarkdownIt("commonmark", {"html": False, "typographer": True}).enable(
    ["table", "strikethrough", "replacements", "smartquotes"]
)


def _fence(
    self: RendererHTML,
    tokens: Sequence[Token],
    idx: int,
    options: Any,
    env: MutableMapping[str, Any],
) -> str:
    code = RendererHTML.fence(self, tokens, idx, options, env)
    if not is_python(tokens[idx]):
        return code
    block = env["blocks"]
    env["blocks"] = block + 1
    outputs = env["outputs"]
    shown = outputs[block] if block < len(outputs) else ""
    return (
        f'<div class="cell" data-block="{block}">{code}'
        '<button type="button" class="run">Run</button>'
        f'<output class="cell-output">{shown}</output></div>\n'
    )


_markdown.add_render_rule("fence", _fence)


def render_markdown(text: str, outputs: Sequence[str] = ()) -> str:
    return _markdown.render(text, {"blocks": 0, "outputs": outputs})
