from functools import partial

from dirsql import DirSQL, Table

from labnotes.models import LabnotesConfig
from labnotes.tables.experiment_toml import experiment_toml
from labnotes.tables.experiments_ddl import experiments_ddl
from labnotes.tables.path_glob import path_glob
from labnotes.tables.read_blocks import read_blocks
from labnotes.tables.read_experiment import read_experiment
from labnotes.tables.read_file import read_file
from labnotes.tables.read_log import read_log
from labnotes.tables.read_run import read_run

FILES = """
CREATE TABLE files (
  experiment TEXT, filename TEXT, path TEXT PRIMARY KEY, ctime TEXT, mtime TEXT,
  mtime_ns INTEGER, content TEXT
)
"""
RUNS = """
CREATE TABLE runs (
  experiment TEXT, id TEXT, folder TEXT, created TEXT, ended TEXT,
  exit_code INTEGER, error TEXT,
  stdout TEXT, stderr TEXT, params TEXT, meta TEXT, run TEXT,
  PRIMARY KEY (experiment, id)
)
"""
# Sizes only: the server reads log text from disk, the row change is the signal.
LOGS = """
CREATE TABLE logs (
  experiment TEXT, run TEXT, stream TEXT, size INTEGER,
  PRIMARY KEY (experiment, run, stream)
)
"""
BLOCKS = """
CREATE TABLE blocks (
  experiment TEXT, run TEXT, size INTEGER,
  PRIMARY KEY (experiment, run)
)
"""


def open_tables(config: LabnotesConfig) -> DirSQL:
    root = config.root
    return DirSQL(
        str(root),
        tables=[
            Table(
                name="files",
                ddl=FILES,
                glob=path_glob(config.files),
                on_file=partial(
                    read_file, root, config.files, experiment=config.experiment
                ),
            ),
            Table(
                name="runs",
                ddl=RUNS,
                glob=path_glob(f"{config.runs}/run.json"),
                on_file=partial(
                    read_run, root, config.runs, experiment=config.experiment
                ),
            ),
            Table(
                name="logs",
                ddl=LOGS,
                glob=path_glob(f"{config.runs}/std*.log"),
                on_file=partial(
                    read_log, root, config.runs, experiment=config.experiment
                ),
            ),
            Table(
                name="blocks",
                ddl=BLOCKS,
                glob=path_glob(f"{config.runs}/log.jsonl"),
                on_file=partial(
                    read_blocks, root, config.runs, experiment=config.experiment
                ),
            ),
            Table(
                name="experiment_configs",
                ddl=experiments_ddl(config),
                glob=path_glob(experiment_toml(config.experiments)),
                on_file=partial(
                    read_experiment,
                    root,
                    config.experiments,
                    experiment=config.experiment,
                    defaults=config.defaults,
                ),
            ),
        ],
        # Run folders are often gitignored (DVC, large outputs); scan them anyway.
        no_ignore=True,
    )
