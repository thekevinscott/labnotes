**Added** — a Restart button on each note with python blocks. It stops that
note's kernel; the next Run starts a fresh one. `--kernel-idle-minutes`
(default 30, also read from `LABNOTES_KERNEL_IDLE_MINUTES`) sets how long a
kernel may sit unused.

**Changed** — a note's kernel now stops after `--kernel-idle-minutes` without
a run, instead of living until the server restarts. Earlier output stays on
the page, but variables do not survive: rerun the blocks they came from.
