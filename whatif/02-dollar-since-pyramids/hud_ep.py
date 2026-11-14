# HUD config for What if #2. Story clock = years since the Great Pyramid (2560 BC), accelerating.
YS = 31556952
# story x in YEARS; $1 per real second for the first clinks, then exponential ramp (log=True)
KEYS = [(0.0, 0.0), (0.4, 1 / YS), (9.3, 9.3 / YS), (11.84, 1 / 365.25), (15.12, 1.0), (22.56, 2560.0), (28.16, 4051.0), (34.88, 4585.0), (48, 4585.0)]
def year(x):
    n = int(x)                      # no year zero: 2560 BC + 2560 years = AD 1
    return f"{2560 - n} BC" if n < 2560 else f"{n - 2559} AD"
EP = dict(
    KEYS=KEYS,
    value=lambda x: max(1, x * YS) if x > 0 else 1,
    fmt=lambda v: "$" + f"{int(v):,}",
    unit="DESMOND'S FAMILY",
    chip=lambda x: f"YEAR {year(x)}",
    pulse=False,
    log=True,
    tags=[(11.84, 13.2, "1 DAY"), (15.4, 18.6, "1 YEAR"), (22.9, 25.0, "ROME"), (26.7, 29.9, "1492"), (35.0, 37.9, "TODAY")],
    show=(0.0, 44.5),
)
