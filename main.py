"""Kaggriculture entry: adaptive demand pocket farmer.

The agent is deliberately stateless.  Every choice is reconstructed from the
official observation so it remains safe after a worker dies, a market order is
rejected, or Kaggle restarts the Python process.

Strategy in one sentence: keep a compact, watered production block, liquidate
only when the shared market is healthy, and pivot new capacity toward products
whose demand is currently being under-served.
"""

from math import inf


# These are published game constants, kept locally to avoid non standard imports
# in Kaggle's submission sandbox.
CROPS = {
    "WHEAT": {"seed": 10, "first": 2, "max": 4, "ongoing": False},
    "CARROT": {"seed": 20, "first": 2, "max": 3, "ongoing": False},
    "TOMATO": {"seed": 50, "first": 8, "max": 8, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first": 10, "max": 10, "ongoing": True},
    "MELON": {"seed": 80, "first": 10, "max": 12, "ongoing": False},
}
ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP", "product": "EGG"},
    "COW": {"cost": 400, "structure": "PASTURE", "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "product": "WOOL"},
}
BASE_PRICE = {
    "WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120,
    "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200,
    "FERTILIZER": 100,
}


def _get(value, name, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _empty_action():
    return {"farmer": ["PASS"], "hands": [], "market": []}


def _market_score(item, prices):
    """A conservative demand signal, normalized around the published price."""
    base = BASE_PRICE.get(item, 1)
    return float(prices.get(item, base)) / base


def _best_crop(prices, day):
    # Fast carrots fund the opening.  Later, demand pockets decide the mix.
    if day < 7:
        return "CARROT"
    candidates = ("CARROT", "TOMATO", "STRAWBERRY", "MELON")
    # Long crops need enough season left to pay back; no speculative late plants.
    # Tomatoes need eight daily care cycles before their first yield.  After
    # day 20 they cannot repay their seed cost reliably before the finale.
    if day > 20:
        candidates = ("CARROT",)
    elif day > 19:
        candidates = ("CARROT", "TOMATO")
    return max(candidates, key=lambda crop: _market_score(crop, prices) / CROPS[crop]["seed"])


def _distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _step_toward(pos, target):
    x, y = pos
    tx, ty = target
    if x < tx:
        return ["EAST"]
    if x > tx:
        return ["WEST"]
    if y < ty:
        return ["SOUTH"]
    if y > ty:
        return ["NORTH"]
    return ["PASS"]


def _tiles(farm):
    return _get(farm, "tiles", []) or []


def _tile_at(farm, pos):
    rows = _tiles(farm)
    x, y = pos
    if 0 <= y < len(rows) and 0 <= x < len(rows[y]):
        return rows[y][x]
    return "LOCKED"


def _all_positions(farm):
    positions = [_get(farm, "farmer", [0, 0])]
    positions.extend(_get(farm, "hands", []) or [])
    return [list(pos) for pos in positions]


def _shed_tiles(board_size):
    half = board_size // 2
    return {(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)}


def _needs_attention(tile, day):
    if not isinstance(tile, dict):
        return False
    if tile.get("kind") == "PLANT":
        # Watering is a survival obligation and becomes a yield action in window.
        return not tile.get("watered_today", False)
    if "animal" in tile:
        return not tile.get("fed_today", False) or not tile.get("cared_today", False)
    return False


def _target_for(pos, farm, day):
    """Choose the closest valuable tile; care has precedence over expansion."""
    best, best_key = None, (inf, inf)
    for y, row in enumerate(_tiles(farm)):
        for x, tile in enumerate(row):
            if tile == "LOCKED":
                continue
            if _needs_attention(tile, day):
                key = (0, _distance(pos, (x, y)))
            elif isinstance(tile, dict) and tile.get("yield_units", 0) > 0:
                key = (1, _distance(pos, (x, y)))
            elif tile is None:
                key = (2, _distance(pos, (x, y)))
            elif isinstance(tile, dict) and tile.get("kind") == "WEED":
                key = (3, _distance(pos, (x, y)))
            else:
                continue
            if key < best_key:
                best, best_key = (x, y), key
    return best


def _urgent_shed_visit(pos, farm, private, board_size):
    """Return the nearest shed tile when a worker lacks a required payload."""
    inventory = _get(private, "inventories", []) or []
    any_wheat = any((inv or {}).get("WHEAT", 0) for inv in inventory)
    animals_need_feed = any(
        isinstance(tile, dict) and "animal" in tile and not tile.get("fed_today", False)
        for row in _tiles(farm) for tile in row
    )
    if animals_need_feed and not any_wheat and (_get(private, "shed", {}) or {}).get("WHEAT", 0):
        return min(_shed_tiles(board_size), key=lambda target: _distance(pos, target))
    return None


def _inventory(private, index):
    inventories = _get(private, "inventories", []) or []
    return inventories[index] if index < len(inventories) else {}


def _unit_action(pos, index, farm, private, day, crop_choice, board_size):
    tile = _tile_at(farm, pos)
    inventory = _inventory(private, index)
    seeds = _get(private, "seeds", {}) or {}
    shed = _get(private, "shed", {}) or {}

    # The shed is the only safe way to arm a worker with fertilizer, wheat, or
    # a purchased animal.  Pick up a focused payload, never a whole shed.
    on_shed = tuple(pos) in _shed_tiles(board_size)
    if on_shed:
        # Animals are moved out first.  Otherwise a farmer can burn an entire
        # day repeatedly collecting wheat while a purchased goose stays stored.
        for animal in ("GOOSE", "COW", "SHEEP"):
            if shed.get(animal, 0) and inventory.get(animal, 0) == 0:
                return ["PICKUP", animal, 1]
        animals_need_feed = any(
            isinstance(candidate, dict) and "animal" in candidate and not candidate.get("fed_today", False)
            for row in _tiles(farm) for candidate in row
        )
        if animals_need_feed and inventory.get("WHEAT", 0) == 0 and shed.get("WHEAT", 0) > 0:
            return ["PICKUP", "WHEAT", min(4, shed["WHEAT"])]
        if inventory.get("FERTILIZER", 0) == 0 and shed.get("FERTILIZER", 0) > 0:
            return ["PICKUP", "FERTILIZER", 1]
        # Deposit harvested products before the 100 item shed cap can surprise us.
        if (not any(inventory.get(animal, 0) for animal in ANIMALS) and
                any(item in BASE_PRICE and item not in ("WHEAT", "FERTILIZER") for item in inventory)):
            return ["DROP"]

    if isinstance(tile, dict):
        if tile.get("kind") == "PLANT":
            crop = tile.get("crop")
            age = day - tile.get("planted_day", day)
            crop_data = CROPS.get(crop, {})
            ripe = age >= crop_data.get("first", 99) and (
                crop_data.get("ongoing", False) or age >= crop_data.get("max", 99) or day >= 29
            )
            if tile.get("yield_units", 0) > 0 and ripe:
                return ["HARVEST"]
            if not tile.get("watered_today", False):
                # Fertilizer is reserved for high value ongoing crops and melon.
                if (crop in ("STRAWBERRY", "TOMATO", "MELON") and
                        inventory.get("FERTILIZER", 0) and tile.get("fertilized_until_day", -1) < day):
                    return ["FERTILIZE"]
                return ["WATER"]
        elif "animal" in tile:
            if not tile.get("fed_today", False) and inventory.get("WHEAT", 0):
                return ["FEED"]
            if not tile.get("cared_today", False):
                return ["CARE"]
            if tile.get("fertilizer_available", False):
                return ["COLLECT_FERTILIZER"]
            if tile.get("yield_units", 0):
                return ["HARVEST"]
        elif tile.get("kind") in ("COOP", "PASTURE"):
            expected = "GOOSE" if tile["kind"] == "COOP" else "COW"
            if inventory.get(expected, 0):
                return ["PLACE", expected]
        elif tile.get("kind") == "WEED":
            return ["DIG"]
    elif tile is None:
        if seeds.get(crop_choice, 0):
            return ["PLANT", crop_choice]
        # A tiny near-shed goose block produces uncrashable eggs and fertilizer.
        if day >= 8 and inventory.get("GOOSE", 0):
            return ["BUILD_COOP"]

    # A structure is not otherwise an attention target.  Explicitly route a
    # worker carrying an animal back to its matching empty structure.
    carried_animal = next((animal for animal in ANIMALS if inventory.get(animal, 0)), None)
    if carried_animal:
        required_structure = ANIMALS[carried_animal]["structure"]
        candidates = [
            (x, y) for y, row in enumerate(_tiles(farm)) for x, candidate in enumerate(row)
            if isinstance(candidate, dict) and candidate.get("kind") == required_structure and "animal" not in candidate
        ]
        if candidates:
            return _step_toward(pos, min(candidates, key=lambda target: _distance(pos, target)))

    target = _urgent_shed_visit(pos, farm, private, board_size) or _target_for(pos, farm, day)
    return _step_toward(pos, target) if target else ["PASS"]


def _market_actions(farm, private, prices, day, crop_choice):
    """Sell in small, price aware batches and protect operational reserves."""
    money = float(_get(farm, "money", 0))
    shed = _get(private, "shed", {}) or {}
    seeds = _get(private, "seeds", {}) or {}
    orders = []
    animal_count = sum(1 for row in _tiles(farm) for tile in row
                       if isinstance(tile, dict) and "animal" in tile)
    # We need wheat for animal feed.  Everything else may be sold, but only at
    # non distressed prices unless the shed is close to capacity.
    for item in ("EGG", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "MILK", "WOOL", "FERTILIZER"):
        amount = int(shed.get(item, 0))
        healthy = _market_score(item, prices) >= 0.82
        if amount and (healthy or sum(shed.values()) > 82):
            orders.append(["SELL", item, min(amount, 18)])
    wheat = int(shed.get("WHEAT", 0))
    wheat_reserve = animal_count * 3
    if wheat > wheat_reserve and _market_score("WHEAT", prices) >= 0.9:
        orders.append(["SELL", "WHEAT", min(wheat - wheat_reserve, 15)])
    if wheat < wheat_reserve and money > prices.get("WHEAT", 25) * 2:
        orders.append(["BUY_PRODUCT", "WHEAT", wheat_reserve - wheat])

    # Orders execute after unit actions. Keep an intentional seed buffer so
    # newly cleared tiles can be planted next turn rather than waiting at shed.
    desired_seeds = 5 if day < 18 else 2
    missing = max(0, desired_seeds - int(seeds.get(crop_choice, 0)))
    if missing and money > CROPS[crop_choice]["seed"] * (missing + 2):
        orders.append(["BUY_SEED", crop_choice, missing])

    # Once early capital is stable, buy geese. They are selected only when egg
    # demand is healthy and a worker can place them from the shed.
    geese_owned = sum(1 for row in _tiles(farm) for tile in row
                      if isinstance(tile, dict) and tile.get("animal") == "GOOSE")
    # Livestock is a midgame conversion, never an opening capital sink.  A
    # stable crop engine and a high price signal must both exist first.
    if day >= 16 and geese_owned < 4 and shed.get("GOOSE", 0) < 1 and money > 8000 and _market_score("EGG", prices) >= 1.05:
        orders.append(["BUY_ANIMAL", "GOOSE", 1])

    # One affordable hand during the productive middle converts idle travel into care.
    hands = _get(farm, "hands", []) or []
    if 8 <= day <= 20 and len(hands) < 1 and money > 5000:
        orders.append(["HIRE"])
    return orders[:10]


def agent(obs):
    """Kaggle entry point. Returns a legal action shape on every observation."""
    farms = _get(obs, "farms", []) or []
    player = int(_get(obs, "player", 0) or 0)
    if player >= len(farms):
        return _empty_action()
    farm = farms[player]
    private = _get(obs, "private", {}) or {}
    market = _get(obs, "market", {}) or {}
    prices = _get(market, "prices", {}) or {}
    day = int(_get(obs, "day", 0) or 0)
    board_size = len(_tiles(farm)) or 10
    crop_choice = _best_crop(prices, day)
    positions = _all_positions(farm)
    actions = [_unit_action(pos, i, farm, private, day, crop_choice, board_size)
               for i, pos in enumerate(positions)]
    return {
        "farmer": actions[0] if actions else ["PASS"],
        "hands": actions[1:],
        "market": _market_actions(farm, private, prices, day, crop_choice),
    }
