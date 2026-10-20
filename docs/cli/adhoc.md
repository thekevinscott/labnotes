# Adhoc

`adhoc` lets you run one-off experiments. `adhoc` is the default mode.

Every `run` plans each combination of `[params]`, `repeats` times, no matter what's already on disk. Use it when each run is its own attempt, like trying a change and looking at the result. An interrupted `run` doesn't resume; the next one starts a new set.

Each `run` gets an invocation folder, named for the UTC time it was planned, and its runs nest inside it:

<Tree>
my-experiment
    runs
        20261020-000429-brave-fox
            quiet-river
</Tree>

If multiple parameters or `repeats` are specified, each run inside the invocation is named from the params that vary:

<Tree>
my-experiment
    runs
        20261020-000429-brave-fox
            opus-low-1a2b
            opus-high-3c4d
            sonnet-low-5e6f
            sonnet-high-7a8b
</Tree>

When nothing varies, the run gets a haiku name instead, like `quiet-river` above.

The frontend groups an `adhoc` experiment's runs by the invocation that made them. When an invocation plans a single run, the CLI opens straight on its output.
