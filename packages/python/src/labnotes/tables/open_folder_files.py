from functools import partial
from pathlib import Path

from dirsql import DirSQL, Table

from labnotes.tables.read_folder_file import read_folder_file

FOLDER_FILES = """
CREATE TABLE files (path TEXT PRIMARY KEY, size INTEGER)
"""


def open_folder_files(folder: Path) -> DirSQL:
    return DirSQL(
        str(folder),
        tables=[
            Table(
                name="files",
                ddl=FOLDER_FILES,
                glob="**",
                on_file=partial(read_folder_file, folder),
            )
        ],
        # Run folders are often gitignored (DVC, large outputs); list them anyway.
        no_ignore=True,
    )
