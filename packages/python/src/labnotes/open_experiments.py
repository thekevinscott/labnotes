from pathlib import Path

from dirsql import DirSQL, Table

from labnotes.read_design import read_design
from labnotes.read_note import read_note


def open_experiments(folder: Path) -> DirSQL:
    return DirSQL(
        str(folder),
        tables=[
            Table(
                name="experiments",
                ddl="CREATE TABLE experiments (name TEXT, study TEXT, design TEXT)",
                glob="*/design.yaml",
                on_file=read_design,
            ),
            Table(
                name="notes",
                ddl="CREATE TABLE notes (experiment TEXT, name TEXT, content TEXT)",
                glob="*/*.md",
                on_file=read_note,
            ),
        ],
    )
