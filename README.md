# Adaptive Demand Pocket Farmer

This is a self contained Kaggriculture submission. Its entry point is
`agent(obs)` in `main.py`.

## Distinctive strategy

The agent does not follow a fixed replay route. Every turn it reads the shared
market, prices its production against the base market, keeps a feed reserve,
and changes its next crop when a demand pocket appears. It combines fast carrot
cash flow with a compact goose block for eggs and fertilizer, then gives care
and harvesting priority over expansion.

## Integrity and submission notes

The submission only uses the Python standard library. It makes no external
network calls, does not require a model download, and returns the official
action schema. Keep `main.py` at the root of the uploaded archive. The current
competition permits five submissions a day and keeps only the newest two active,
so use paired replay testing before replacing an active entry.
