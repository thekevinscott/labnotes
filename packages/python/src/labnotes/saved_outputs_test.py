from unittest import mock

from labnotes.saved_outputs import saved_outputs


def test_without_a_kernel_nothing_has_run() -> None:
    assert saved_outputs(None, "```python\na\n```\n") == []


def test_matches_outputs_to_blocks_by_code() -> None:
    with mock.patch("labnotes.saved_outputs.block_key", side_effect=str.strip):
        kernel = mock.Mock(outputs={"b": "<b>"})

        assert saved_outputs(kernel, "```python\na\n```\n\n```python\nb\n```\n") == [
            "",
            "<b>",
        ]
