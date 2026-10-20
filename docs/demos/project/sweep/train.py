import argparse
import random
import time

parser = argparse.ArgumentParser()
parser.add_argument("--output")
parser.add_argument("--model")
parser.add_argument("--effort")
args = parser.parse_args()

steps = random.randint(8, 14)
for step in range(1, steps + 1):
    print(f"step {step}/{steps} model={args.model} effort={args.effort} loss={1 / step:.3f}", flush=True)
    time.sleep(0.7)
