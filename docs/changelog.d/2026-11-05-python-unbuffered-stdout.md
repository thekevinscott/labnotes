Fixed: runs now set `PYTHONUNBUFFERED=1`, so a Python script's stdout reaches `stdout.log` as it is printed and survives a stop or timeout. A `PYTHONUNBUFFERED` you set yourself is kept.
