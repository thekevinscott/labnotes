from functools import partial

from dirsql import DirSQL, Table

from labnotes.models import LabnotesConfig
from labnotes.tables.file_prefix import file_prefix
from labnotes.tables.open_tables import FILES
from labnotes.tables.path_glob import path_glob
from labnotes.tables.read_file import read_file


def open_note_tables(config: LabnotesConfig, experiment: str) -> DirSQL | None:
    prefix = file_prefix(config.files)
    folder = config.root / prefix.replace("{experiment}", experiment)
    if not folder.is_dir() or not folder.resolve().is_relative_to(
        config.root.resolve()
    ):
        return None
    return DirSQL(
        str(folder),
        tables=[
            Table(
                name="files",
                ddl=FILES,
                glob=path_glob(config.files[len(prefix) :]) or "**",
                on_file=partial(
                    read_file, config.root, config.files, experiment=config.experiment
                ),
            )
        ],
        no_ignore=True,
    )
