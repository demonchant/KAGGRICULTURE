"""Seat-balanced candidate-vs-baseline replay benchmark."""

import importlib.util
from pathlib import Path
import sys

from main import agent as candidate
from smoke_test import run


def load_agent(path):
    spec = importlib.util.spec_from_file_location("three_cow_baseline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


def main():
    seeds = [int(value) for value in sys.argv[1:]] or list(range(1, 101))
    baseline = load_agent(Path(".baseline-three-cow/main.py"))
    margins = []
    for seed in seeds:
        forward = run(seed, agents=(candidate, baseline))
        reverse = run(seed, agents=(baseline, candidate))
        margin = (forward[0] - forward[1] + reverse[1] - reverse[0]) / 2
        margins.append(margin)
        print(f"seed={seed} paired_margin={margin:.0f}")
    print(f"mean paired margin={sum(margins) / len(margins):.1f} "
          f"wins={sum(margin > 0 for margin in margins)}/{len(margins)}")


if __name__ == "__main__":
    main()
