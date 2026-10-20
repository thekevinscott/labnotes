## Summary

`labnotes server` drops `--kernel-idle-minutes`; kernels no longer stop when idle.

## Required changes

| Before | After |
| --- | --- |
| `labnotes server --kernel-idle-minutes 10` | `labnotes server` (the flag is now an error) |
| `LABNOTES_KERNEL_IDLE_MINUTES=10` | remove it; it is ignored |

## Deprecations removed

None.
