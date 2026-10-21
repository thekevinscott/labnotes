# Adhoc

`adhoc` lets you run one-off experiments. `adhoc` is the default mode.

Every `run` plans each combination of `[params]`, `repeats` times, no matter what's already on disk. Use it when each run is its own attempt, like trying a change and looking at the result. An interrupted `run` doesn't resume; the next one starts a new set.

A `run` that plans a single run writes one folder, named for the UTC time it was planned:

<Tree>
my-experiment
    runs
        20261020-000429-brave-fox/
</Tree>

When multiple parameters or `repeats` give a `run` more than one run, it gets an invocation folder with that name, and its runs nest inside it, each named from the params that vary:

<Tree>
my-experiment
    runs
        20261020-000429-brave-fox
            opus-low-1a2b/
            opus-high-3c4d/
            sonnet-low-5e6f/
            sonnet-high-7a8b/
</Tree>

When nothing varies but `repeats` is more than 1, the nested runs get haiku names instead, like `quiet-river`.

The frontend groups an `adhoc` experiment's runs by the invocation that made them. When an invocation plans a single run, the CLI opens straight on its output.
