Fixed: a stopped or timed-out run now records the script's own exit code after it shuts down within the 5-second grace, instead of the shell's `-15`, and memory is sampled until the script exits.
