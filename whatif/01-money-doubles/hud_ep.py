# HUD config for What if #1. Story clock = seconds since Rico's first coin; voice-tight timings (Bomba gap 1.3 s after "buried").
import json, os
G = 1.3                                     # Bomba gap inserted at 28.1 s
KEYS = [(0.0, 0.0), (9.68, 10.0), (16.88, 17.0), (21.28, 20.0), (25.36, 25.0), (28.24 + G, 30.0), (39.44 + G, 38.0), (46.9 + G, 41.0)]
EP = dict(
    KEYS=KEYS,
    value=lambda x: 2 ** int(x),
    unit="COINS",
    chip=lambda x: f"T + {int(x)} s",
    tags=[(13.1, 13.9, "POCKETS: RIP"), (19.8, 21.1, "≈ 1 TON"), (23.6, 25.2, "> 1 ELEPHANT"),
          (31.2 + G, 33.6 + G, "1 BILLION"), (40.4 + G, 43.6 + G, "2,000,000 TONS")],
    show=(0.0, 46.9 + G),
)
