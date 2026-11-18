from pathlib import Path

from labnotes.tables.read_folder_file import read_folder_file


def test_lists_a_file_by_its_path_inside_the_folder(tmp_path: Path) -> None:
    path = tmp_path / "ckpt/epoch-1.pt"
    path.parent.mkdir()
    path.write_bytes(b"abc")

    assert read_folder_file(tmp_path, str(path)) == [
        {"path": "ckpt/epoch-1.pt", "size": 3}
    ]


def test_skips_a_file_that_is_gone_before_it_is_read(tmp_path: Path) -> None:
    assert read_folder_file(tmp_path, str(tmp_path / "gone.txt")) == []
