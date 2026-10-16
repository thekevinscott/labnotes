import hashlib
from functools import cache
from pathlib import Path
from typing import Any

from jinja2 import pass_context

STATIC = Path(__file__).parent / "static"


@cache
def _digest(path: str) -> str:
    return hashlib.sha256((STATIC / path).read_bytes()).hexdigest()[:12]


@pass_context
def asset_url(context: Any, path: str) -> str:
    # Browsers (Safari especially) hold onto static files across releases.
    return f"{context['request'].url_for('static', path=path)}?v={_digest(path)}"
