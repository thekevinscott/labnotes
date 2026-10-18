# Which runs count toward repeats, unless experiment.toml sets `counts`.
DEFAULT_COUNTS = "exit_code = 0 AND NOT coalesce(run ->> 'excluded', false)"
