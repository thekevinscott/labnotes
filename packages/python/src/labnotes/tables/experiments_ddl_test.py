from unittest import mock

from labnotes.tables.experiments_ddl import experiments_ddl


def test_many_experiments_without_defaults_keep_a_null_config() -> None:
    ddl = experiments_ddl(mock.Mock(experiment=None, defaults={}))

    assert "coalesce(experiment_configs.config, NULL)" in ddl
    assert "UNION SELECT experiment FROM runs\n" in ddl


def test_falls_back_to_the_defaults_as_json() -> None:
    ddl = experiments_ddl(mock.Mock(experiment=None, defaults={"command": "it's"}))

    assert """coalesce(experiment_configs.config, '{"command": "it''s"}')""" in ddl


def test_lists_the_one_experiment() -> None:
    ddl = experiments_ddl(mock.Mock(experiment="study", defaults={}))

    assert "UNION SELECT experiment FROM runs\n      UNION SELECT 'study'\n" in ddl
