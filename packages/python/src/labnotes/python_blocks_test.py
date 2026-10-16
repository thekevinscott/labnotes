from unittest import mock

from labnotes.python_blocks import is_python, python_blocks


def test_finds_plain_python_fences_in_order() -> None:
    text = (
        "# Title\n\n```python\nx = 1\n```\n\nprose\n\n"
        "```py\nskipped\n```\n\n```\nbare\n```\n\n```python title\nx + 1\n```\n"
    )

    assert python_blocks(text) == ["x = 1\n", "x + 1\n"]


def test_ignores_indented_code_and_other_languages() -> None:
    assert python_blocks("    x = 1\n\n```js\nlet x\n```\n") == []


def test_is_python_requires_a_fence() -> None:
    assert not is_python(mock.Mock(type="code_block", info="python"))
