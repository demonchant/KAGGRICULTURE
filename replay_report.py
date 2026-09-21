"""Summarize final rewards, seat effects, and daily market pressure in a replay."""

import json
import sys
from collections import Counter
from pathlib import Path


def daily_snapshot(replay, day):
    step = min(day * 24, len(replay["steps"]) - 1)
    observation = replay["steps"][step][0]["observation"]
    market = observation["market"]
    return market["prices"], market["inventory"]


def main():
    path = Path(sys.argv[1])
    replay = json.loads(path.read_text(encoding="utf8"))
    print(f"episode={replay['info'].get('EpisodeId')} rewards={replay['rewards']}")
    print(f"teams={replay['info'].get('TeamNames')}")
    for day in (0, 8, 14, 20, 29):
        prices, inventory = daily_snapshot(replay, day)
        print(f"day={day} milk_price={prices['MILK']} milk_inventory={inventory['MILK']} "
              f"wool_price={prices['WOOL']} wool_inventory={inventory['WOOL']}")
    action_counts = [Counter(), Counter()]
    for step in replay["steps"][1:]:
        for player, state in enumerate(step):
            action = state.get("action", {})
            farmer = action.get("farmer", ["PASS"])
            action_counts[player][farmer[0]] += 1
    for player, counts in enumerate(action_counts):
        print(f"player={player} farmer_ops={dict(counts)}")


if __name__ == "__main__":
    main()
