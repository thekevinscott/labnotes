import json

from labnotes.models import LabnotesConfig
from labnotes.sql_quote import quote_string

# experiments is a view, so files and runs can't declare a foreign key to it.
EXPERIMENTS = """
CREATE TABLE experiment_configs (
  experiment TEXT PRIMARY KEY, config TEXT, source TEXT
);
CREATE VIEW experiments AS
  SELECT name, coalesce(config ->> 'name', name) AS display_name, config, source
  FROM (
    SELECT
      names.name,
      coalesce(experiment_configs.config, {defaults}) AS config,
      experiment_configs.source
    FROM (
      SELECT experiment AS name FROM experiment_configs
      UNION SELECT experiment FROM files
      UNION SELECT experiment FROM runs{one}
    ) AS names
    LEFT JOIN experiment_configs ON experiment_configs.experiment = names.name
  );
"""


def experiments_ddl(config: LabnotesConfig) -> str:
    defaults = json.dumps(config.defaults, default=str) if config.defaults else None
    one = config.experiment
    return EXPERIMENTS.format(
        defaults="NULL" if defaults is None else quote_string(defaults),
        one="" if one is None else f"\n      UNION SELECT {quote_string(one)}",
    )
