import posixpath
import re
from functools import partial

from dirsql import DirSQL, Table

from labnotes.models import LabnotesConfig
from labnotes.tables.experiment_toml import experiment_toml
from labnotes.tables.experiments_ddl import experiments_ddl
from labnotes.tables.open_tables import BLOCKS, FILES, LOGS, MEMORY, RUN_FILES, RUNS
from labnotes.tables.path_glob import path_glob
from labnotes.tables.read_blocks import read_blocks
from labnotes.tables.read_experiment import read_experiment
from labnotes.tables.read_file import read_file
from labnotes.tables.read_log import read_log
from labnotes.tables.read_memory import read_memory
from labnotes.tables.read_run import read_run
from labnotes.tables.read_run_file import read_run_file

PATTERN = re.compile(r"[{*?\[]")


def open_experiment_tables(config: LabnotesConfig, name: str) -> DirSQL:
    experiments = config.experiments.replace("{experiment}", name)
    files = config.files.replace("{experiment}", name)
    runs = config.runs.replace("{experiment}", name)
    folder = posixpath.commonpath(
        [
            PATTERN.split(template)[0].rpartition("/")[0]
            for template in (experiment_toml(experiments), files, runs)
        ]
    )
    root = config.root

    def glob(template: str) -> str:
        return path_glob(template[len(folder) :].lstrip("/"))

    return DirSQL(
        str(root / folder),
        tables=[
            Table(
                name="files",
                ddl=FILES,
                glob=glob(files),
                on_file=partial(read_file, root, files, experiment=name),
            ),
            Table(
                name="runs",
                ddl=RUNS,
                glob=glob(f"{runs}/run.json"),
                on_file=partial(read_run, root, runs, experiment=name),
            ),
            Table(
                name="logs",
                ddl=LOGS,
                glob=glob(f"{runs}/std*"),
                on_file=partial(read_log, root, runs, experiment=name),
            ),
            Table(
                name="blocks",
                ddl=BLOCKS,
                glob=glob(f"{runs}/log.jsonl"),
                on_file=partial(read_blocks, root, runs, experiment=name),
            ),
            Table(
                name="memory",
                ddl=MEMORY,
                glob=glob(f"{runs}/memory.jsonl"),
                on_file=partial(read_memory, root, runs, experiment=name),
            ),
            Table(
                name="experiment_configs",
                ddl=experiments_ddl(config),
                glob=glob(experiment_toml(experiments)),
                on_file=partial(
                    read_experiment,
                    root,
                    experiments,
                    experiment=name,
                    defaults=config.defaults,
                ),
            ),
            Table(
                name="run_files",
                ddl=RUN_FILES,
                glob=glob(f"{runs}/**"),
                on_file=partial(read_run_file, root, runs, experiment=name),
            ),
        ],
        # Run folders are often gitignored (DVC, large outputs); scan them anyway.
        no_ignore=True,
    )
