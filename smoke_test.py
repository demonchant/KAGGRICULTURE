"""Offline rules smoke test using Kaggle's official interpreter source.

This is deliberately dependency free. It substitutes only the small utility
function imported by the official environment, then runs a full season against
the bundled starter bot. It is not a score claim: use paired replay experiments
before judging a strategy change.
"""

from pathlib import Path
import sys
from types import SimpleNamespace

from main import agent


class Dot(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__


def load_official(seed):
    source = Path("simulator_reference.py").read_text(encoding="utf8")
    source = source.replace(
        "from kaggle_environments.utils import resolve_episode_seed",
        f"def resolve_episode_seed(env): return {seed}",
    )
    namespace = {"__file__": str(Path("simulator_reference.py").resolve())}
    exec(compile(source, "official_kaggriculture.py", "exec"), namespace)
    return namespace


def run(seed=20260921, trace=False):
    game = load_official(seed)
    configuration = Dot(boardSize=10, startingMoney=3000, episodeSteps=721,
                        turnsPerDay=24, maxMarketOrdersPerTurn=10,
                        farmHandCostMult=1, shedCapacity=100,
                        townShopUnlockInterval=3, townShopSellInterval=4,
                        townCenterSellInterval=24)
    state = [SimpleNamespace(observation=Dot(), action=None, reward=0, status="ACTIVE")
             for _ in range(2)]
    env = SimpleNamespace(configuration=configuration, steps=[], done=False, info={"seed": seed})
    game["interpreter"](state, env)
    for step in range(720):
        state[0].observation.step = step
        state[1].observation.step = step
        state[0].action = agent(state[0].observation)
        if trace and 192 <= step <= 199:
            print("trace", step, state[0].observation.farms[0]["farmer"], state[0].action)
        state[1].action = game["starter_agent"](state[1].observation)
        game["interpreter"](state, env)
    first, second = state[0].reward, state[1].reward
    assert first >= 0 and second >= 0
    if trace:
        print(f"seed={seed} adaptive={first:.0f} starter={second:.0f} margin={first - second:.0f}")
        print("adaptive shed", dict(state[0].observation.private["shed"]))
        print("adaptive seeds", dict(state[0].observation.private["seeds"]))
    return first, second


if __name__ == "__main__":
    seeds = [int(value) for value in sys.argv[1:]] or [20260921]
    results = [run(seed) for seed in seeds]
    for seed, (first, second) in zip(seeds, results):
        print(f"seed={seed} adaptive={first:.0f} starter={second:.0f} margin={first - second:.0f}")
    margins = [first - second for first, second in results]
    print(f"mean margin={sum(margins) / len(margins):.1f} wins={sum(margin > 0 for margin in margins)}/{len(margins)}")
