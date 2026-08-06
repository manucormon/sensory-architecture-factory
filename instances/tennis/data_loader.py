"""
Tennis instance — data "loading".

DECLARED, not REAL: there is no real match to read. This generates a
synthetic point-by-point timeline, 1 sample per second, informed by
published match structure (not measured from any real player):
  - a point: 4-12s of play (rally), declared/illustrative
  - between points: 20-25s recovery — ATP/WTA shot clock, a real,
    citable rule, unlike the rally timing above
  - changeover: 90s recovery, every odd game — also a real rule

Returns a list of samples: {phase, t, in_point, reflex_event, point_progress}
"""

import random


def build_synthetic_game(seed=7, n_points=6):
    rng = random.Random(seed)
    samples = []
    t = 0

    for point_i in range(n_points):
        point_len = rng.randint(4, 12)
        reflex_offsets = {0}  # the serve is always a reflex-tier event
        if point_len > 6 and rng.random() < 0.5:
            reflex_offsets.add(rng.randint(2, point_len - 2))  # a mid-rally smash/volley

        for offset in range(point_len):
            samples.append({
                "phase": "point",
                "t": t,
                "in_point": True,
                "reflex_event": offset in reflex_offsets,
                "point_progress": offset / max(point_len - 1, 1),
            })
            t += 1

        is_changeover = (point_i % 2 == 1)  # illustrative alternation, not the real odd-game rule
        gap = 90 if is_changeover else rng.randint(20, 25)
        for _ in range(gap):
            samples.append({
                "phase": "changeover" if is_changeover else "between_points",
                "t": t,
                "in_point": False,
                "reflex_event": False,
                "point_progress": 0.0,
            })
            t += 1

    return samples


def load(seed=7, n_points=6):
    return build_synthetic_game(seed=seed, n_points=n_points)
