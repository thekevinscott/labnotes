from functools import partial

from dirsql import DirSQL, Table

from labnotes.models import LabnotesConfig
from labnotes.tables.path_glob import path_glob
from labnotes.tables.read_experiment import read_experiment
from labnotes.tables.read_file import read_file
from labnotes.tables.read_run import read_run

# experiments is a view, so files and runs can't declare a foreign key to it.
EXPERIMENTS = """
CREATE TABLE experiment_configs (experiment TEXT PRIMARY KEY, config TEXT);
CREATE VIEW experiments AS
  SELECT
    names.name,
    coalesce(experiment_configs.config ->> 'name', names.name) AS display_name,
    experiment_configs.config
  FROM (
    SELECT experiment AS name FROM experiment_configs
    UNION SELECT experiment FROM files
    UNION SELECT experiment FROM runs
  ) AS names
  LEFT JOIN experiment_configs ON experiment_configs.experiment = names.name;
"""
FILES = """
CREATE TABLE files (
  experiment TEXT, filename TEXT, path TEXT PRIMARY KEY, ctime TEXT, mtime TEXT
)
"""
RUNS = """
CREATE TABLE runs (
  experiment TEXT, id TEXT, folder TEXT, created TEXT, ended TEXT,
  exit_code INTEGER, error TEXT, stdout TEXT, stderr TEXT, params TEXT,
  PRIMARY KEY (experiment, id)
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
                on_file=partial(read_file, root, config.files),
            ),
            Table(
                name="runs",
                ddl=RUNS,
                glob=path_glob(f"{config.runs}/run.json"),
                on_file=partial(read_run, root, config.runs),
            ),
            Table(
                name="experiment_configs",
                ddl=EXPERIMENTS,
                glob=path_glob(f"{config.experiments}/experiment.toml"),
                on_file=partial(read_experiment, root, config.experiments),
            ),
        ],
        # Run folders are often gitignored (DVC, large outputs); scan them anyway.
        no_ignore=True,
    )
