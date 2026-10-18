**Added** — `labnotes experiments NAME run` runs an experiment from its
`experiment.toml`: every `[params]` combination, `repeats` times, round-robin,
`--concurrency N` at a time. Each run gets a new folder with `run.json`,
`stdout.log` and `stderr.log`. Only exit-0 runs count, so running again fills
the gaps. Ctrl-C stops the runs; a second Ctrl-C kills them. `-e PATH` reads
another experiment file.
