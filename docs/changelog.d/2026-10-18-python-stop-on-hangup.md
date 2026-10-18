**Fixed** — `labnotes experiments NAME run` now stops and records its runs on SIGTERM or SIGHUP, as it does on Ctrl-C. Before, closing the terminal left the runs going untracked.
