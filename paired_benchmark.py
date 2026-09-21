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
    forward_margins, reverse_margins = [], []
    for seed in seeds:
        forward = run(seed, agents=(candidate, baseline))
        reverse = run(seed, agents=(baseline, candidate))
        forward_margin = forward[0] - forward[1]
        reverse_margin = reverse[1] - reverse[0]
        forward_margins.append(forward_margin)
        reverse_margins.append(reverse_margin)
        print(f"seed={seed} seat0_margin={forward_margin:.0f} "
              f"seat1_margin={reverse_margin:.0f}")
    for label, margins in (("seat0", forward_margins), ("seat1", reverse_margins)):
        print(f"{label} mean={sum(margins) / len(margins):.1f} "
              f"wins={sum(margin > 0 for margin in margins)}/{len(margins)}")


if __name__ == "__main__":
    main()
