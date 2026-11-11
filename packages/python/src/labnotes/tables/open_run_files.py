from functools import partial
from pathlib import Path

from dirsql import DirSQL, Table

from labnotes.models import LabnotesConfig
from labnotes.tables.open_tables import RUN_FILES
from labnotes.tables.read_run_file import read_run_file


def open_run_files(config: LabnotesConfig, folder: Path) -> DirSQL:
    return DirSQL(
        str(folder),
        tables=[
            Table(
                name="run_files",
                ddl=RUN_FILES,
                glob="**",
                on_file=partial(
                    read_run_file,
                    config.root,
                    config.runs,
                    experiment=config.experiment,
                ),
            )
        ],
        no_ignore=True,
    )
