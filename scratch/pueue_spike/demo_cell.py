"""A labnotes-style cell: prints progress, spawns a child, exits 0 on SIGTERM after cleanup."""

import signal
import subprocess
import sys
import time

seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 60
child = subprocess.Popen(["sleep", "3600"])


def on_term(*_: object) -> None:
    print("got SIGTERM, cleaning up", flush=True)
    child.terminate()
    sys.exit(0)


signal.signal(signal.SIGTERM, on_term)
start = time.time()
while time.time() - start < seconds:
    print(f"tick {time.time() - start:.0f}", flush=True)
    print("warn", file=sys.stderr, flush=True)
    time.sleep(1)
child.terminate()
print("done", flush=True)
