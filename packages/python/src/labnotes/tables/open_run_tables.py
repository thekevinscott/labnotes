from collections.abc import Callable
from functools import partial
from pathlib import Path

from dirsql import DirSQL, Table

from labnotes.models import LabnotesConfig
from labnotes.tables.open_tables import BLOCKS, LOGS, RUNS
from labnotes.tables.read_blocks import read_blocks
from labnotes.tables.read_log import read_log
from labnotes.tables.read_run import read_run


def open_run_tables(config: LabnotesConfig, folder: Path) -> DirSQL:
    def table(
        name: str, ddl: str, glob: str, read: Callable[..., list[dict[str, object]]]
    ) -> Table:
        on_file = partial(read, config.root, config.runs, experiment=config.experiment)
        return Table(name=name, ddl=ddl, glob=glob, on_file=on_file)

    return DirSQL(
        str(folder),
        tables=[
            table("runs", RUNS, "run.json", read_run),
            table("logs", LOGS, "std*", read_log),
            table("blocks", BLOCKS, "log.jsonl", read_blocks),
        ],
        no_ignore=True,
    )
