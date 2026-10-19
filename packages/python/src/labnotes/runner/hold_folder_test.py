from pathlib import Path

import pytest

from labnotes.runner.hold_folder import hold_folder


def test_holds_a_folder_until_the_block_ends(tmp_path: Path) -> None:
    with hold_folder(tmp_path):
        with pytest.raises(BlockingIOError):
            with hold_folder(tmp_path):
                pass

    with hold_folder(tmp_path):
        pass

    assert [*tmp_path.iterdir()] == []
